import os
from urllib.parse import quote

import httpx


class AnalysisProviderError(RuntimeError):
    pass


def provider_label() -> str:
    provider = os.getenv("AI_PROVIDER", "ollama").strip().lower()
    return {"ollama": "Ollama", "cloudflare": "Cloudflare"}.get(provider, "AI")


def _selected_provider() -> str:
    provider = os.getenv("AI_PROVIDER", "ollama").strip().lower()
    if provider not in {"ollama", "cloudflare"}:
        raise AnalysisProviderError("AI_PROVIDER must be either 'ollama' or 'cloudflare'.")
    return provider


def _ollama_chat_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/api/chat"


async def chat_completion(base_url: str, model: str, prompt: str, operation: str) -> str:
    provider = _selected_provider()
    if provider == "ollama":
        provider_name = "Ollama"
        url = _ollama_chat_url(base_url)
        request_model = model
        headers = None
        payload = {
            "model": request_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json",
            "think": False,
        }
    else:
        provider_name = "Cloudflare"
        account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
        api_token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
        missing = [
            name
            for name, value in (
                ("CLOUDFLARE_ACCOUNT_ID", account_id),
                ("CLOUDFLARE_API_TOKEN", api_token),
            )
            if not value
        ]
        if missing:
            raise AnalysisProviderError(
                f"Cloudflare is not configured: set {', '.join(missing)}."
            )
        request_model = os.getenv(
            "CLOUDFLARE_MODEL", "@cf/zai-org/glm-4.7-flash"
        ).strip() or "@cf/zai-org/glm-4.7-flash"
        url = (
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{quote(account_id, safe='')}/ai/v1/chat/completions"
        )
        headers = {"Authorization": f"Bearer {api_token}"}
        payload = {
            "model": request_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "response_format": {"type": "json_object"},
        }

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            request_options = {"json": payload}
            if headers is not None:
                request_options["headers"] = headers
            response = await client.post(url, **request_options)
            response.raise_for_status()
            body = response.json()
            if provider == "ollama":
                content = body["message"]["content"]
            else:
                content = body["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as exc:
        raise AnalysisProviderError(
            f"{provider_name} {operation} returned HTTP {exc.response.status_code}."
        ) from exc
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
        raise AnalysisProviderError(
            f"{provider_name} {operation} failed ({type(exc).__name__})."
        ) from exc

    if not isinstance(content, str):
        raise AnalysisProviderError(
            f"{provider_name} {operation} returned an invalid response."
        )
    return content
