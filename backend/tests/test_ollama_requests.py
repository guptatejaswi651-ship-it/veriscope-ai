import json
import unittest
from unittest.mock import patch

import httpx

from agents.conflict_agent import find_conflicts
from agents.verification_agent import verify


class OllamaRequestTests(unittest.IsolatedAsyncioTestCase):
    base_url = "http://ollama.test:11434/"
    model = "qwen3.5:4b"
    sources = [{"id": 1, "title": "Source", "url": "https://example.com", "snippet": "Evidence"}]

    async def _mock_request(self, request, response_body):
        requests = []
        timeouts = []

        async def mock_post(_client, url, **kwargs):
            requests.append((url, kwargs))
            timeouts.append(_client.timeout.read)

            class Response:
                def raise_for_status(self):
                    pass

                def json(self):
                    return {"message": {"content": json.dumps(response_body)}}

            return Response()

        with patch.object(httpx.AsyncClient, "post", new=mock_post):
            result = await request

        self.assertEqual(len(requests), 1)
        url, kwargs = requests[0]
        self.assertEqual(url, "http://ollama.test:11434/api/chat")
        self.assertEqual(dict(httpx.URL(url).params), {})
        self.assertEqual(timeouts, [120])
        self.assertNotIn("x-goog-api-key", kwargs.get("headers", {}))
        payload = kwargs["json"]
        self.assertEqual(payload["model"], self.model)
        self.assertEqual(payload["messages"][0]["role"], "user")
        self.assertIn("Question?", payload["messages"][0]["content"])
        self.assertIs(payload["stream"], False)
        self.assertEqual(payload["format"], "json")
        self.assertIs(payload["think"], False)
        return result

    async def test_verification_uses_ollama_and_preserves_validation(self):
        result = await self._mock_request(
            verify("Question?", self.sources, self.base_url, self.model),
            {
                "summary": "Reviewed",
                "findings": [{"title": "Finding", "detail": "Detail", "source_ids": [1, 7]}],
                "claims": [
                    {"text": "Claim", "status": "Supported", "explanation": "Evidence", "source_ids": [1]},
                    {"text": "Uncited", "status": "Supported", "explanation": "No reference", "source_ids": []},
                ],
                "assessment": "Reviewed",
            },
        )
        self.assertEqual(result["findings"][0]["source_ids"], [1])
        self.assertEqual(result["claims"][0]["status"], "Supported")
        self.assertEqual(result["claims"][1]["status"], "Insufficient evidence")

    async def test_conflict_review_uses_ollama_and_validates_source_ids(self):
        sources = self.sources + [
            {"id": 2, "title": "Second source", "url": "https://example.org", "snippet": "More evidence"},
        ]
        result = await self._mock_request(
            find_conflicts("Question?", sources, self.base_url, self.model),
            {"conflicts": [
                {"title": "Disagreement", "explanation": "Different accounts", "source_ids": [1, 2, 2, 7]},
                {"title": "Incomplete", "explanation": "One source only", "source_ids": [1]},
            ]},
        )
        self.assertEqual(result, [{
            "title": "Disagreement",
            "explanation": "Different accounts",
            "source_ids": [1, 2],
        }])


if __name__ == "__main__":
    unittest.main()
