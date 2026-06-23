"""Phase B: /api/health/ready behaviour."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_ready_returns_200_when_all_checks_pass(client: TestClient):
    """Healthy app returns 200."""
    r = client.get("/api/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "app_db" in body["checks"]


def test_ready_returns_503_when_db_unreachable(monkeypatch, client: TestClient):
    """Mock DB failure to force 503."""
    import alejandria.routers.health as h

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, *_):
            raise RuntimeError("simulated DB outage")

    monkeypatch.setattr(h, "SessionLocal", FakeSession)
    r = client.get("/api/health/ready")
    assert r.status_code == 503
    assert r.json()["status"] == "degraded"
    assert r.json()["checks"]["app_db"]["status"] == "error"


def test_health_unchanged_liveness(client: TestClient):
    """The liveness endpoint is a pure process check."""
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
