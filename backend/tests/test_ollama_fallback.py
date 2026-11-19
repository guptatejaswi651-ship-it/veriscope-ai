import asyncio
import os
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient

os.environ["DATABASE_PATH"] = "/tmp/veriscope-route-tests.db"
from main import app
from agents.verification_agent import AnalysisProviderError


class OllamaFallbackTests(unittest.TestCase):
    source = {
        "id": 1,
        "title": "Retrieved source",
        "url": "https://example.com/source",
        "domain": "example.com",
        "published_at": None,
        "retrieved_at": "2026-11-18T00:00:00+00:00",
        "snippet": "Retrieved evidence.",
    }

    def setUp(self):
        self.context = TestClient(app)
        self.client = self.context.__enter__()
        self.environment = patch.dict(
            os.environ,
            {
                "TAVILY_API_KEY": "test-tavily-key",
                "AI_PROVIDER": "ollama",
                "OLLAMA_BASE_URL": "http://ollama.test:11434/",
                "OLLAMA_MODEL": "qwen3.5:4b",
            },
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def tearDown(self):
        self.context.__exit__(None, None, None)

    def test_ollama_verification_failure_returns_and_saves_sources_without_analysis(self):
        with (
            patch("routers.research.search", new=AsyncMock(return_value=[self.source])),
            patch(
                "routers.research.verify",
                new=AsyncMock(side_effect=AnalysisProviderError("Ollama verification returned HTTP 503.")),
            ) as verify_mock,
            patch("routers.research.find_conflicts", new=AsyncMock(return_value=[])) as find_conflicts,
        ):
            response = self.client.post("/api/research", json={"question": "A test research question"})

        self.assertEqual(response.status_code, 200)
        report = response.json()
        self.assertEqual(report["sources"], [self.source])
        self.assertIn("System-generated status message", report["summary"])
        self.assertIn("not an AI-generated research summary", report["summary"])
        self.assertIn("1 real source(s)", report["summary"])
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["claims"], [])
        self.assertEqual(report["conflicts"], [])
        self.assertEqual(report["agents_status"]["verification"]["status"], "unavailable")
        self.assertEqual(report["agents_status"]["conflict"]["status"], "unavailable")
        self.assertIn("503", report["agents_status"]["verification"]["message"])
        self.assertTrue(any("AI verification could not be completed" in item for item in report["limitations"]))
        find_conflicts.assert_awaited_once()
        self.assertEqual(
            report["agents_status"]["conflict"]["message"],
            "Conflict result was not included because verification was unavailable.",
        )
        verify_mock.assert_awaited_once_with(
            "A test research question",
            [self.source],
            "http://ollama.test:11434",
            "qwen3.5:4b",
        )
        self.assertEqual(self.client.get(f"/api/research/{report['research_id']}").json(), report)

    def test_ollama_conflict_failure_preserves_successful_verification(self):
        analysis = {
            "summary": "A source-backed summary.",
            "findings": [{"title": "Finding", "detail": "Evidence detail.", "source_ids": [1]}],
            "claims": [{"text": "Claim", "status": "Supported", "explanation": "Evidence supports it.", "source_ids": [1]}],
            "assessment": "Evidence supports the claim.",
        }
        with (
            patch("routers.research.search", new=AsyncMock(return_value=[self.source])),
            patch("routers.research.verify", new=AsyncMock(return_value=analysis)) as verify_mock,
            patch(
                "routers.research.find_conflicts",
                new=AsyncMock(side_effect=AnalysisProviderError("Ollama conflict review failed (TimeoutException).")),
            ) as conflict_mock,
        ):
            response = self.client.post("/api/research", json={"question": "A test research question"})

        self.assertEqual(response.status_code, 200)
        report = response.json()
        self.assertEqual(report["summary"], analysis["summary"])
        self.assertEqual(report["findings"], analysis["findings"])
        self.assertEqual(report["claims"], analysis["claims"])
        self.assertEqual(report["conflicts"], [])
        self.assertEqual(report["agents_status"]["verification"]["status"], "completed")
        self.assertEqual(report["agents_status"]["conflict"]["status"], "unavailable")
        self.assertTrue(any("AI conflict analysis could not be completed" in item for item in report["limitations"]))
        verify_mock.assert_awaited_once_with(
            "A test research question",
            [self.source],
            "http://ollama.test:11434",
            "qwen3.5:4b",
        )
        conflict_mock.assert_awaited_once_with(
            "A test research question",
            [self.source],
            "http://ollama.test:11434",
            "qwen3.5:4b",
        )

    def test_verification_and_conflict_agents_are_dispatched_concurrently(self):
        started = set()
        both_started = None

        async def wait_for_both(name):
            nonlocal both_started
            if both_started is None:
                both_started = asyncio.Event()
            started.add(name)
            if len(started) == 2:
                both_started.set()
            await asyncio.wait_for(both_started.wait(), timeout=1)

        async def verify_concurrently(*_args):
            await wait_for_both("verification")
            return {
                "summary": "Evidence summary.",
                "findings": [],
                "claims": [],
                "assessment": "Evidence reviewed.",
            }

        async def conflicts_concurrently(*_args):
            await wait_for_both("conflict")
            return []

        with (
            patch("routers.research.search", new=AsyncMock(return_value=[self.source])),
            patch("routers.research.verify", new=AsyncMock(side_effect=verify_concurrently)) as verify_mock,
            patch(
                "routers.research.find_conflicts",
                new=AsyncMock(side_effect=conflicts_concurrently),
            ) as conflict_mock,
        ):
            response = self.client.post("/api/research", json={"question": "A test research question"})

        self.assertEqual(response.status_code, 200)
        verify_mock.assert_awaited_once()
        conflict_mock.assert_awaited_once()
        self.assertEqual(started, {"verification", "conflict"})

    def test_cloudflare_analysis_failure_uses_existing_report_fallback(self):
        with (
            patch.dict(
                os.environ,
                {
                    "AI_PROVIDER": "cloudflare",
                    "CLOUDFLARE_ACCOUNT_ID": "test-account",
                    "CLOUDFLARE_API_TOKEN": "test-token",
                    "TAVILY_API_KEY": "test-tavily-key",
                },
            ),
            patch("routers.research.search", new=AsyncMock(return_value=[self.source])),
            patch(
                "httpx.AsyncClient.post",
                new=AsyncMock(side_effect=httpx.ReadTimeout("mocked timeout")),
            ) as provider_post,
        ):
            response = self.client.post("/api/research", json={"question": "A test research question"})

        self.assertEqual(response.status_code, 200)
        report = response.json()
        self.assertEqual(report["sources"], [self.source])
        self.assertEqual(report["agents_status"]["verification"]["status"], "unavailable")
        self.assertEqual(report["agents_status"]["conflict"]["status"], "unavailable")
        self.assertIn("Cloudflare verification", report["agents_status"]["verification"]["message"])
        self.assertNotIn("test-token", response.text)
        self.assertEqual(provider_post.await_count, 2)


if __name__ == "__main__":
    unittest.main()
