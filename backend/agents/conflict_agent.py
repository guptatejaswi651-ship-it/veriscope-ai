import json
from agents.ai_provider import AnalysisProviderError, chat_completion, provider_label

async def find_conflicts(question: str, sources: list[dict], base_url: str, model: str) -> list[dict]:
    evidence = "\n".join(
        f"[{s['id']}] {s['title']} ({s['url']})\nPublished: {s.get('published_at') or 'unknown'}\nExcerpt: {s['snippet']}"
        for s in sources
    )
    prompt = f'''Compare the evidence excerpts for direct factual disagreements relevant to this question. Return valid JSON only: {{"conflicts":[{{"title":"short description","explanation":"describe the disagreement and plausible date, scope, definition, or method differences without declaring either source false","source_ids":[1,2]}}]}}. Only report a conflict if at least two cited excerpts directly disagree. If none are evidenced, return an empty array. Use no facts outside these excerpts.\nQuestion: {question}\nEvidence:\n{evidence}'''
    raw = await chat_completion(base_url, model, prompt, "conflict review")
    try:
        result = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise AnalysisProviderError(
            f"{provider_label()} conflict review failed ({type(exc).__name__})."
        ) from exc
    if not isinstance(result, dict) or not isinstance(result.get("conflicts", []), list):
        raise AnalysisProviderError(f"{provider_label()} conflict review returned an invalid response.")

    valid_ids = {source["id"] for source in sources}
    conflicts = []
    for item in result.get("conflicts", []):
        if not isinstance(item, dict):
            raise AnalysisProviderError(f"{provider_label()} conflict review returned an invalid response.")
        ids = []
        reported_ids = item.get("source_ids", [])
        if not isinstance(reported_ids, list):
            reported_ids = []
        for value in reported_ids:
            try:
                source_id = int(value)
            except (TypeError, ValueError):
                continue
            if source_id in valid_ids and source_id not in ids:
                ids.append(source_id)
        if len(ids) >= 2:
            conflicts.append({
                "title": str(item.get("title", "Source disagreement")),
                "explanation": str(item.get("explanation", "")),
                "source_ids": ids,
            })
    return conflicts
