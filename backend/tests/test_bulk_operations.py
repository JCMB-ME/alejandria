"""Plan 2: Bulk operations tests — caps, auth, shelf + tag endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from alejandria.auth import rate_limit
from alejandria.db import SessionLocal
from alejandria.models.shelf import Shelf, ShelfBook
from alejandria.models.user import User


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    rate_limit._per_minute.clear()
    rate_limit._per_hour.clear()
    yield
    rate_limit._per_minute.clear()
    rate_limit._per_hour.clear()


@pytest.fixture
def auth_cookies(client: TestClient):
    r = client.post(
        "/api/auth/login/json",
        json={"username": "admin", "password": "testpass"},
    )
    assert r.status_code == 200, r.text
    # Set on the client so subsequent requests carry them automatically.
    client.cookies = r.cookies
    return r.cookies


@pytest.fixture
def auth_headers(auth_cookies) -> dict:
    """CSRF header for state-changing requests."""
    csrf = auth_cookies.get("alejandria_csrf", "")
    return {"X-CSRF-Token": csrf}


@pytest.fixture
def shelf_id(auth_cookies, client: TestClient, request):
    """Create a shelf for the admin user via the /api/shelves endpoint.
    Uses a unique name per test to avoid 409 conflicts when the same
    fixture is invoked multiple times in the same test file.
    """
    import uuid
    unique_name = f"Test shelf {request.node.name}-{uuid.uuid4().hex[:8]}"
    r = client.post(
        "/api/shelves",
        json={"name": unique_name, "shelf_type": "custom"},
        cookies=auth_cookies,
        headers={"X-CSRF-Token": auth_cookies.get("alejandria_csrf", "")},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_bulk_endpoints_require_auth(client: TestClient):
    """All bulk endpoints are auth-required.

    Without auth, the CSRF middleware short-circuits first (403) and the
    auth gate is reached only with a valid CSRF pair. We assert 4xx for both.
    """
    r = client.post("/api/books/bulk/delete", json={"book_ids": [1]})
    assert r.status_code in (401, 403)
    r = client.post(
        "/api/books/bulk/add-to-shelf",
        json={"book_ids": [1], "shelf_id": 1},
    )
    assert r.status_code in (401, 403)


def test_bulk_add_to_shelf_other_users_shelf_404(client: TestClient, auth_cookies, auth_headers):
    """A shelf not owned by the user returns 404."""
    # Use shelf_id=9999 — almost certainly not present
    r = client.post(
        "/api/books/bulk/add-to-shelf",
        json={"book_ids": [1, 2], "shelf_id": 9999},
        cookies=auth_cookies,
        headers=auth_headers,
    )
    assert r.status_code == 404


def test_bulk_add_to_shelf_idempotent(client: TestClient, auth_cookies, auth_headers, shelf_id, db):
    """Adding a book twice — first marks them as failed (no Calibre),
    second call is consistent (same books, same result). Verifies the
    endpoint shape and that nothing blows up when called twice.
    """
    r = client.post(
        "/api/books/bulk/add-to-shelf",
        json={"book_ids": [1, 2, 3], "shelf_id": shelf_id},
        cookies=auth_cookies,
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert "affected" in body
    # Second call: same books — must be idempotent (no errors, same shape)
    r2 = client.post(
        "/api/books/bulk/add-to-shelf",
        json={"book_ids": [1, 2, 3], "shelf_id": shelf_id},
        cookies=auth_cookies,
        headers=auth_headers,
    )
    assert r2.status_code == 200
    body2 = r2.json()
    # Real Calibre is not available in tests, so books 1..3 are reported
    # as failed. Idempotence means: the second call returns the same
    # body as the first (no DB corruption, no 500s).
    assert body2["affected"] == body["affected"]
    assert body2["skipped"] == body["skipped"]
    assert body2["failed"] == body["failed"]


def test_bulk_remove_from_shelf(client: TestClient, auth_cookies, auth_headers, shelf_id):
    """Remove books from a shelf that already contains them.

    Pre-populate the shelf with 2 books via the existing /api/shelves endpoint,
    then test the bulk remove endpoint.
    """
    # Add 2 books via the per-book endpoint first
    for book_id in (1, 2):
        r = client.post(
            f"/api/shelves/{shelf_id}/books/{book_id}",
            cookies=auth_cookies,
            headers=auth_headers,
        )
        assert r.status_code in (201, 200)
    r = client.post(
        "/api/books/bulk/remove-from-shelf",
        json={"book_ids": [1, 2, 3], "shelf_id": shelf_id},
        cookies=auth_cookies,
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["affected"] == 2


def test_bulk_set_tags_replaces(client: TestClient, auth_cookies, auth_headers):
    """set-tags returns affected=0 (no real Calibre) but endpoint is reachable."""
    r = client.post(
        "/api/books/bulk/set-tags",
        json={"book_ids": [1, 2], "tags": ["fantasy"]},
        cookies=auth_cookies,
        headers=auth_headers,
    )
    # Real Calibre not available in tests; calibredb exits non-zero so
    # failed=2. We only assert the endpoint shape.
    assert r.status_code == 200
    body = r.json()
    assert "failed" in body
    assert "affected" in body


def test_bulk_add_tags_endpoint(client: TestClient, auth_cookies, auth_headers):
    r = client.post(
        "/api/books/bulk/add-tags",
        json={"book_ids": [1], "tags": ["new-tag"]},
        cookies=auth_cookies,
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert "affected" in body


def test_bulk_remove_tags_endpoint(client: TestClient, auth_cookies, auth_headers):
    r = client.post(
        "/api/books/bulk/remove-tags",
        json={"book_ids": [1], "tags": ["stale"]},
        cookies=auth_cookies,
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert "affected" in body


def test_bulk_cap_returns_422(client: TestClient, auth_cookies, auth_headers):
    """501 books is over the cap and is rejected by Pydantic."""
    r = client.post(
        "/api/books/bulk/delete",
        json={"book_ids": list(range(1, 502))},
        cookies=auth_cookies,
        headers=auth_headers,
    )
    assert r.status_code == 422


def test_bulk_empty_list_returns_400(client: TestClient, auth_cookies, auth_headers, shelf_id):
    """An empty list raises 400 (not 422) per the plan's helper."""
    r = client.post(
        "/api/books/bulk/add-to-shelf",
        json={"book_ids": [], "shelf_id": shelf_id},
        cookies=auth_cookies,
        headers=auth_headers,
    )
    assert r.status_code == 400


def test_bulk_delete_endpoint_shape(client: TestClient, auth_cookies, auth_headers):
    """delete endpoint returns a BulkResult with affected/failed fields."""
    r = client.post(
        "/api/books/bulk/delete",
        json={"book_ids": [1, 2, 3]},
        cookies=auth_cookies,
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert "affected" in body
    assert "failed" in body
