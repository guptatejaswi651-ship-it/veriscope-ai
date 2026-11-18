import json
import os
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

os.environ["DATABASE_PATH"] = "/tmp/veriscope-route-tests.db"
from main import app


class ReportChatTests(unittest.TestCase):
    report = {
        "research_id": "saved-report-1",
        "summary": "The report summarizes source-backed evidence.",
        "findings": [{"title": "Finding one", "detail": "A relevant detail.", "source_ids": [1]}],
        "claims": [{"text": "A claim", "status": "Supported", "explanation": "The source supports it.", "source_ids": [1]}],
        "sources": [{
            "id": 1,
            "title": "Source one",
            "url": "https://example.com/source-one",
            "domain": "example.com",
            "published_at": None,
            "retrieved_at": "2026-11-18T00:00:00+00:00",
            "snippet": "Evidence excerpt.",
        }],
    }

    def setUp(self):
        self.context = TestClient(app)
        self.client = self.context.__enter__()

    def tearDown(self):
        self.context.__exit__(None, None, None)

    def test_ask_endpoint_uses_mocked_ollama_and_filters_source_ids(self):
        requests = []

        async def mock_post(_client, url, **kwargs):
            requests.append((url, kwargs))

            class Response:
                def raise_for_status(self):
                    pass

                def json(self):
                    return {
                        "message": {
                            "content": json.dumps({
                                "answer": "The report's finding is supported by Source one.",
                                "source_ids": [1, 999, 1],
                            }),
                        },
                    }

            return Response()

        with (
            patch.dict(
                os.environ,
                {
                    "OLLAMA_BASE_URL": "http://ollama.test:11434/",
                    "OLLAMA_MODEL": "qwen3.5:4b",
                },
            ),
            patch("routers.research.get_report", return_value=self.report),
            patch.object(httpx.AsyncClient, "post", new=mock_post),
        ):
            response = self.client.post(
                "/api/research/saved-report-1/ask",
                json={"question": "What supports the finding?"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "answer": "The report's finding is supported by Source one.",
            "source_ids": [1],
        })
        self.assertEqual(len(requests), 1)
        url, kwargs = requests[0]
        self.assertEqual(url, "http://ollama.test:11434/api/chat")
        payload = kwargs["json"]
        self.assertEqual(payload["model"], "qwen3.5:4b")
        self.assertIs(payload["stream"], False)
        self.assertEqual(payload["format"], "json")
        self.assertIs(payload["think"], False)
        prompt = payload["messages"][0]["content"]
        self.assertIn(self.report["summary"], prompt)
        self.assertIn(self.report["findings"][0]["detail"], prompt)
        self.assertIn(self.report["claims"][0]["text"], prompt)
        self.assertIn(self.report["sources"][0]["url"], prompt)
        self.assertIn("What supports the finding?", prompt)

    def test_ask_endpoint_returns_404_for_missing_saved_report(self):
        with (
            patch("routers.research.get_report", return_value=None),
            patch.object(httpx.AsyncClient, "post") as ollama_post,
        ):
            response = self.client.post(
                "/api/research/missing-report/ask",
                json={"question": "What does this report say?"},
            )

        self.assertEqual(response.status_code, 404)
        ollama_post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
