import json
import os
import unittest
from unittest.mock import patch

import httpx

from agents.conflict_agent import find_conflicts
from agents.report_chat_agent import answer_report_question
from agents.verification_agent import AnalysisProviderError, verify


class AIProviderTests(unittest.IsolatedAsyncioTestCase):
    base_url = "http://ollama.test:11434"
    local_model = "qwen3.5:4b"
    sources = [
        {"id": 1, "title": "Source one", "url": "https://example.com/one", "snippet": "Evidence one"},
        {"id": 2, "title": "Source two", "url": "https://example.com/two", "snippet": "Evidence two"},
    ]
    report = {
        "summary": "Evidence summary",
        "findings": [],
        "claims": [],
        "sources": sources,
    }

    def _environment(self, provider):
        values = {"AI_PROVIDER": provider}
        if provider == "cloudflare":
            values.update({
                "CLOUDFLARE_ACCOUNT_ID": "test-account",
                "CLOUDFLARE_API_TOKEN": "test-cloudflare-token",
                "CLOUDFLARE_MODEL": "@cf/zai-org/glm-4.7-flash",
            })
        return patch.dict(os.environ, values)

    async def test_cloudflare_normalizes_responses_for_all_analysis_agents(self):
        responses = [
            {
                "summary": "Reviewed",
                "findings": [{"title": "Finding", "detail": "Evidence", "source_ids": [1]}],
                "claims": [{"text": "Claim", "status": "Supported", "explanation": "Evidence", "source_ids": [1]}],
                "assessment": "Supported by evidence",
            },
            {"conflicts": [{"title": "Difference", "explanation": "Accounts differ", "source_ids": [1, 2]}]},
            {"answer": "The report supports the claim.", "source_ids": [1]},
        ]
        requests = []

        async def mock_post(_client, url, **kwargs):
            requests.append((url, kwargs))
            content = json.dumps(responses[len(requests) - 1])

            class Response:
                def raise_for_status(self):
                    pass

                def json(self):
                    return {"choices": [{"message": {"content": content}}]}

            return Response()

        with (
            self._environment("cloudflare"),
            patch.object(httpx.AsyncClient, "post", new=mock_post),
        ):
            verification = await verify("Question?", self.sources, self.base_url, self.local_model)
            conflicts = await find_conflicts("Question?", self.sources, self.base_url, self.local_model)
            answer = await answer_report_question("What supports it?", self.report, self.base_url, self.local_model)

        self.assertEqual(verification["summary"], "Reviewed")
        self.assertEqual(verification["claims"][0]["source_ids"], [1])
        self.assertEqual(conflicts[0]["source_ids"], [1, 2])
        self.assertEqual(answer, {"answer": "The report supports the claim.", "source_ids": [1]})
        self.assertEqual(len(requests), 3)
        expected_url = (
            "https://api.cloudflare.com/client/v4/accounts/test-account/"
            "ai/v1/chat/completions"
        )
        for url, kwargs in requests:
            self.assertEqual(url, expected_url)
            self.assertEqual(kwargs["headers"], {"Authorization": "Bearer test-cloudflare-token"})
            self.assertEqual(kwargs["json"]["model"], "@cf/zai-org/glm-4.7-flash")
            self.assertEqual(kwargs["json"]["response_format"], {"type": "json_object"})
            self.assertIs(kwargs["json"]["stream"], False)

    async def _verify_with_mock(self, provider, mock_post):
        with (
            self._environment(provider),
            patch.object(httpx.AsyncClient, "post", new=mock_post),
        ):
            return await verify("Question?", self.sources, self.base_url, self.local_model)

    async def test_both_providers_reject_malformed_responses(self):
        async def malformed_post(_client, _url, **_kwargs):
            class Response:
                def raise_for_status(self):
                    pass

                def json(self):
                    return {"unexpected": "shape"}

            return Response()

        for provider in ("ollama", "cloudflare"):
            with self.subTest(provider=provider):
                with self.assertRaises(AnalysisProviderError) as caught:
                    await self._verify_with_mock(provider, malformed_post)
                self.assertIn("failed (KeyError)", str(caught.exception))

    async def test_both_providers_reject_malformed_json_content(self):
        async def malformed_json_post(_client, url, **_kwargs):
            content = "{not-json"

            class Response:
                def raise_for_status(self):
                    pass

                def json(self):
                    message = {"content": content}
                    if "api.cloudflare.com" in url:
                        return {"choices": [{"message": message}]}
                    return {"message": message}

            return Response()

        for provider in ("ollama", "cloudflare"):
            with self.subTest(provider=provider):
                with self.assertRaises(AnalysisProviderError) as caught:
                    await self._verify_with_mock(provider, malformed_json_post)
                self.assertIn("JSONDecodeError", str(caught.exception))

    async def test_invalid_source_id_containers_are_filtered(self):
        response_data = {
            "summary": "Reviewed",
            "findings": [{"title": "Finding", "detail": "Evidence", "source_ids": 1}],
            "claims": [{"text": "Claim", "status": "Supported", "explanation": "Evidence", "source_ids": None}],
            "assessment": "Reviewed",
        }

        async def mock_post(_client, url, **_kwargs):
            class Response:
                def raise_for_status(self):
                    pass

                def json(self):
                    content = json.dumps(response_data)
                    if "api.cloudflare.com" in url:
                        return {"choices": [{"message": {"content": content}}]}
                    return {"message": {"content": content}}

            return Response()

        for provider in ("ollama", "cloudflare"):
            with self.subTest(provider=provider):
                with self._environment(provider), patch.object(
                    httpx.AsyncClient, "post", new=mock_post
                ):
                    result = await verify("Question?", self.sources, self.base_url, self.local_model)
                self.assertEqual(result["findings"][0]["source_ids"], [])
                self.assertEqual(result["claims"][0]["status"], "Insufficient evidence")

    async def test_both_providers_report_timeouts_without_leaking_credentials(self):
        async def timeout_post(_client, _url, **_kwargs):
            raise httpx.ReadTimeout("mocked timeout")

        for provider in ("ollama", "cloudflare"):
            with self.subTest(provider=provider):
                with self.assertRaises(AnalysisProviderError) as caught:
                    await self._verify_with_mock(provider, timeout_post)
                self.assertIn("ReadTimeout", str(caught.exception))
                self.assertNotIn("test-cloudflare-token", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
