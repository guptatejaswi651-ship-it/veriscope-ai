import json
import httpx

class AnalysisProviderError(RuntimeError):
    pass

def _ollama_chat_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/api/chat"

async def verify(question: str, sources: list[dict], base_url: str, model: str) -> dict:
    evidence = "\n".join(
        f"[{s['id']}] {s['title']} ({s['url']})\nPublished: {s.get('published_at') or 'unknown'}\nExcerpt: {s['snippet']}"
        for s in sources
    )
    prompt = f'''Act as a careful fact-checking analyst. Use only the provided source excerpts. Return valid JSON with keys: summary (string), findings (array of {{title, detail, source_ids}}), claims (array of {{text, status, explanation, source_ids}}), assessment (string). A claim status must be Supported, Contradicted, or Insufficient evidence. Use Supported or Contradicted only when direct source evidence justifies it. Cite source IDs from the list. Do not invent facts, dates, or sources. Mention material limitations. Keep at most 8 claims and 6 findings.\nQuestion: {question}\nEvidence:\n{evidence}'''
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(_ollama_chat_url(base_url), json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "format": "json",
                "think": False,
            })
            response.raise_for_status()
            raw = response.json()["message"]["content"]
            result = json.loads(raw)
    except httpx.HTTPStatusError as exc:
        raise AnalysisProviderError(f"Ollama verification returned HTTP {exc.response.status_code}.") from exc
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
        raise AnalysisProviderError(f"Ollama claim analysis failed ({type(exc).__name__}).") from exc

    valid_ids = {source["id"] for source in sources}
    for group in ("findings", "claims"):
        for item in result.get(group, []):
            source_ids = []
            for value in item.get("source_ids", []):
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
