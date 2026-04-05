"""QuotedBy — API E2E tests.

Run against a live server on port 8891:
  cd /Users/exzent/reddit_scout/services/quotedby
  uv run uvicorn quotedby.main:app --port 8891 &
  uv run pytest tests/test_api.py -v
"""
from __future__ import annotations

import httpx
import pytest

BASE = "http://127.0.0.1:8891"


@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=BASE, timeout=60) as c:
        yield c


@pytest.fixture(scope="module")
def project_id(client: httpx.Client) -> int:
    """Create a test project and return its ID. Cleaned up after tests."""
    resp = client.post("/projects", json={
        "name": "TestQuotedBy",
        "category": "test automation",
        "competitors": ["CompA", "CompB"],
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "TestQuotedBy"
    assert len(data["queries"]) > 0
    yield data["id"]
    # Cleanup
    client.delete(f"/projects/{data['id']}")


class TestHealth:
    def test_health(self, client: httpx.Client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "2.0.0"


class TestModels:
    def test_get_available_models(self, client: httpx.Client):
        resp = client.get("/models")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 8
        first = data[0]
        assert "id" in first
        assert "name" in first
        assert "provider" in first

    def test_suggest_queries(self, client: httpx.Client):
        resp = client.get("/suggest-queries", params={"name": "TestProd", "category": "analytics", "count": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert "queries" in data
        assert len(data["queries"]) == 5


class TestProjects:
    def test_create_project(self, client: httpx.Client, project_id: int):
        # project_id fixture already creates the project
        assert project_id > 0

    def test_list_projects(self, client: httpx.Client, project_id: int):
        resp = client.get("/projects")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert any(p["id"] == project_id for p in data)

    def test_get_project(self, client: httpx.Client, project_id: int):
        resp = client.get(f"/projects/{project_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == project_id
        assert data["name"] == "TestQuotedBy"
        assert data["category"] == "test automation"
        assert data["competitors"] == ["CompA", "CompB"]

    def test_get_project_not_found(self, client: httpx.Client):
        resp = client.get("/projects/999999")
        assert resp.status_code == 404

    def test_update_project(self, client: httpx.Client, project_id: int):
        resp = client.patch(f"/projects/{project_id}", json={"name": "TestQuotedBy Updated"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "TestQuotedBy Updated"
        # Restore
        client.patch(f"/projects/{project_id}", json={"name": "TestQuotedBy"})


class TestDashboard:
    def test_dashboard(self, client: httpx.Client, project_id: int):
        resp = client.get(f"/projects/{project_id}/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == project_id
        assert "visibility_score" in data
        assert "by_model" in data
        assert "recommendations" in data

    def test_dashboard_not_found(self, client: httpx.Client):
        resp = client.get("/projects/999999/dashboard")
        assert resp.status_code == 404


class TestTrends:
    def test_trends(self, client: httpx.Client, project_id: int):
        resp = client.get(f"/projects/{project_id}/trends", params={"days": 7})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_trends_not_found(self, client: httpx.Client):
        resp = client.get("/projects/999999/trends")
        assert resp.status_code == 404


class TestScan:
    def test_scan_with_models(self, client: httpx.Client, project_id: int):
        """Run a scan with specific model IDs."""
        resp = client.post(
            f"/projects/{project_id}/scan",
            json={"model_ids": ["qwen/qwen3-30b-a3b:free"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == project_id
        assert data["scanned_models"] == 1
        assert data["total_checks"] > 0
        assert "results" in data
        assert "mentions_found" in data
        assert "mention_rate_pct" in data

    def test_scan_no_body(self, client: httpx.Client, project_id: int):
        """Scan with default models when no body is provided."""
        resp = client.post(f"/projects/{project_id}/scan")
        assert resp.status_code == 200
        data = resp.json()
        assert data["scanned_models"] == 3  # 3 default models

    def test_scan_not_found(self, client: httpx.Client):
        resp = client.post("/projects/999999/scan")
        assert resp.status_code == 404

    def test_results(self, client: httpx.Client, project_id: int):
        resp = client.get(f"/projects/{project_id}/results", params={"limit": 10})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)


class TestDefamation:
    def test_defamation_check_endpoint_exists(self, project_id: int):
        """Verify defamation-check endpoint is reachable (uses longer timeout)."""
        with httpx.Client(base_url=BASE, timeout=180) as long_client:
            resp = long_client.post(f"/projects/{project_id}/defamation-check")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_checks" in data
        assert "critical" in data
        assert "warnings" in data
        assert "clean" in data
        assert "results" in data

    def test_defamation_history(self, client: httpx.Client, project_id: int):
        resp = client.get(f"/projects/{project_id}/defamation", params={"limit": 10})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_defamation_not_found(self, client: httpx.Client):
        resp = client.post("/projects/999999/defamation-check")
        assert resp.status_code == 404
