import json

from agents.ai_provider import (
    AnalysisProviderError,
    _ollama_chat_url,
    chat_completion,
    provider_label,
)

async def verify(question: str, sources: list[dict], base_url: str, model: str) -> dict:
    evidence = "\n".join(
        f"[{s['id']}] {s['title']} ({s['url']})\nPublished: {s.get('published_at') or 'unknown'}\nExcerpt: {s['snippet']}"
        for s in sources
    )
    prompt = f'''Act as a careful fact-checking analyst. Use only the provided source excerpts. Return valid JSON with keys: summary (string), findings (array of {{title, detail, source_ids}}), claims (array of {{text, status, explanation, source_ids}}), assessment (string). A claim status must be Supported, Contradicted, or Insufficient evidence. Use Supported or Contradicted only when direct source evidence justifies it. Cite source IDs from the list. Do not invent facts, dates, or sources. Mention material limitations. Keep at most 8 claims and 6 findings.\nQuestion: {question}\nEvidence:\n{evidence}'''
    raw = await chat_completion(base_url, model, prompt, "verification")
    try:
        result = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise AnalysisProviderError(
            f"{provider_label()} verification failed ({type(exc).__name__})."
        ) from exc
    if not isinstance(result, dict):
        raise AnalysisProviderError(f"{provider_label()} verification returned an invalid response.")

    valid_ids = {source["id"] for source in sources}
    for group in ("findings", "claims"):
        items = result.get(group, [])
        if not isinstance(items, list):
            raise AnalysisProviderError(f"{provider_label()} verification returned an invalid response.")
        for item in items:
            if not isinstance(item, dict):
                raise AnalysisProviderError(f"{provider_label()} verification returned an invalid response.")
            source_ids = []
            reported_ids = item.get("source_ids", [])
            if not isinstance(reported_ids, list):
                reported_ids = []
            for value in reported_ids:
                try:
                    source_id = int(value)
                except (TypeError, ValueError):
                    continue
                if source_id in valid_ids and source_id not in source_ids:
                    source_ids.append(source_id)
            item["source_ids"] = source_ids
            if group == "claims":
                if item.get("status") not in {"Supported", "Contradicted", "Insufficient evidence"}:
                    item["status"] = "Insufficient evidence"
                if item["status"] in {"Supported", "Contradicted"} and not source_ids:
                    item["status"] = "Insufficient evidence"
                    item["explanation"] = "No valid source reference was returned; this claim cannot be marked supported or contradicted."
    result.setdefault("summary", "Evidence review completed.")
    result.setdefault("findings", [])
    result.setdefault("claims", [])
    result.setdefault("assessment", "Evidence reviewed; see findings and limitations.")
    return result
