import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
os.environ["DATABASE_PATH"] = "/tmp/veriscope-route-tests.db"
from main import app

class RouteRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.context = TestClient(app)
        self.client = self.context.__enter__()

    def tearDown(self):
        self.context.__exit__(None, None, None)

    def test_existing_routes_remain_registered(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/health").status_code, 200)

    def test_required_routes_are_in_openapi(self):
        paths = self.client.get("/openapi.json").json()["paths"]
        self.assertIn("post", paths["/api/research"])
        self.assertIn("get", paths["/api/research/{research_id}"])
        self.assertIn("get", paths["/api/history"])

    def test_history_and_missing_report(self):
        self.assertEqual(self.client.get("/api/history").status_code, 200)
        self.assertEqual(self.client.get("/api/research/not-a-real-id").status_code, 404)

    def test_invalid_or_unconfigured_research_is_not_fabricated(self):
        self.assertEqual(self.client.post("/api/research", json={"question": "  "}).status_code, 422)
        with patch.dict(os.environ, {"TAVILY_API_KEY": ""}):
            response = self.client.post("/api/research", json={"question": "A meaningful research question"})
        self.assertEqual(response.status_code, 503)
        self.assertIn("TAVILY_API_KEY", response.json()["detail"])

if __name__ == "__main__":
    unittest.main()
