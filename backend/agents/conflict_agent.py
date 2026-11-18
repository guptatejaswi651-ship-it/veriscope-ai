import json
import httpx
from agents.verification_agent import _ollama_chat_url, AnalysisProviderError

async def find_conflicts(question: str, sources: list[dict], base_url: str, model: str) -> list[dict]:
    evidence = "\n".join(
        f"[{s['id']}] {s['title']} ({s['url']})\nPublished: {s.get('published_at') or 'unknown'}\nExcerpt: {s['snippet']}"
        for s in sources
    )
    prompt = f'''Compare the evidence excerpts for direct factual disagreements relevant to this question. Return valid JSON only: {{"conflicts":[{{"title":"short description","explanation":"describe the disagreement and plausible date, scope, definition, or method differences without declaring either source false","source_ids":[1,2]}}]}}. Only report a conflict if at least two cited excerpts directly disagree. If none are evidenced, return an empty array. Use no facts outside these excerpts.\nQuestion: {question}\nEvidence:\n{evidence}'''
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
        raise AnalysisProviderError(f"Ollama conflict review returned HTTP {exc.response.status_code}.") from exc
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
        raise AnalysisProviderError(f"Ollama conflict review failed ({type(exc).__name__}).") from exc

    valid_ids = {source["id"] for source in sources}
    conflicts = []
    for item in result.get("conflicts", []):
        ids = []
        for value in item.get("source_ids", []):
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
