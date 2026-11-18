from datetime import datetime, timezone
from urllib.parse import urlparse
import httpx

TAVILY_URL = "https://api.tavily.com/search"

class ResearchProviderError(RuntimeError):
    pass

async def search(question: str, api_key: str) -> list[dict]:
    """Fetch current sources from Tavily; never synthesize source records."""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(TAVILY_URL, json={
                "api_key": api_key,
                "query": question,
                "search_depth": "advanced",
                "max_results": 8,
                "include_answer": False,
                "include_raw_content": False,
            })
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPStatusError as exc:
        raise ResearchProviderError(f"Tavily returned HTTP {exc.response.status_code}.") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise ResearchProviderError(f"Tavily request failed ({type(exc).__name__}).") from exc

    retrieved_at = datetime.now(timezone.utc).isoformat()
    sources = []
    for result in payload.get("results", []):
        url = result.get("url")
        if not url:
            continue
        sources.append({
            "id": len(sources) + 1,
            "title": result.get("title") or url,
            "url": url,
            "domain": urlparse(url).netloc,
            "published_at": result.get("published_date"),
            "retrieved_at": retrieved_at,
            "snippet": result.get("content") or "",
        })
    if not sources:
        raise ResearchProviderError("Tavily returned no usable source records; research was not completed.")
    return sources
