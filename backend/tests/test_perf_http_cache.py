"""Phase C7: HTTP cache headers + ETag."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from alejandria.main import create_app


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


def test_library_stats_returns_etag(client: TestClient):
    """First call returns ETag header."""
    r = client.get("/api/library/stats")
    assert r.status_code == 200
    assert "ETag" in r.headers
    assert "Cache-Control" in r.headers
    assert "max-age=60" in r.headers["Cache-Control"]


def test_library_stats_304_on_matching_if_none_match(client: TestClient):
    """Second call with If-None-Match returns 304."""
    r1 = client.get("/api/library/stats")
    etag = r1.headers["ETag"]
    r2 = client.get("/api/library/stats", headers={"If-None-Match": etag})
    assert r2.status_code == 304
    assert r2.headers["ETag"] == etag
    assert r2.content == b""


def test_books_list_returns_etag(client: TestClient):
    """Books list sets ETag + Cache-Control."""
    r = client.get("/api/books?page=1&page_size=10")
    assert r.status_code == 200
    assert "ETag" in r.headers
    assert "Cache-Control" in r.headers


def test_books_list_304_on_matching_if_none_match(client: TestClient):
    """Books list 304 on matching ETag."""
    r1 = client.get("/api/books?page=1&page_size=10")
    etag = r1.headers["ETag"]
    r2 = client.get(
        "/api/books?page=1&page_size=10",
        headers={"If-None-Match": etag},
    )
    assert r2.status_code == 304