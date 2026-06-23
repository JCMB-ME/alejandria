"""Plan 3 (Highlights Complete): PATCH 403/404, color validator, export zip/per-book.

Tests are integration-level (FastAPI TestClient) because the audit findings
(R3, R4, H4) are observable only at the HTTP boundary. The CSRF middleware
is active — non-GET requests carry the X-CSRF-Token header.
"""

from __future__ import annotations

import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from alejandria.auth import rate_limit
from alejandria.auth.security import hash_password
from alejandria.db import SessionLocal
from alejandria.models.user import User, UserRole
from alejandria.services import calibre_db as calibre_db_module


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    rate_limit._per_minute.clear()
    rate_limit._per_hour.clear()
    yield
    rate_limit._per_minute.clear()
    rate_limit._per_hour.clear()


def _login(client: TestClient, username: str, password: str) -> dict:
    r = client.post(
        "/api/auth/login/json",
        json={"username": username, "password": password},
    )
    assert r.status_code == 200, r.text
    client.cookies = r.cookies
    return dict(r.cookies)


@pytest.fixture
def auth_cookies(client: TestClient):
    return _login(client, "admin", "testpass")


@pytest.fixture
def auth_headers(auth_cookies) -> dict:
    """CSRF header for state-changing requests."""
    return {"X-CSRF-Token": auth_cookies.get("alejandria_csrf", "")}


@pytest.fixture
def second_user(client: TestClient):
    """Create a second non-admin user and return its cookies."""
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == "second_user").first()
        if existing:
            db.delete(existing)
            db.commit()
        u = User(
            username="second_user",
            password_hash=hash_password("secondpass"),
            role=UserRole.USER,
            is_active=True,
            display_name="Second",
        )
        db.add(u)
        db.commit()
        db.refresh(u)
    finally:
        db.close()
    cookies = _login(client, "second_user", "secondpass")
    return cookies


class _FakeCalibreDB:
    """Minimal stand-in for CalibreDB used by the export tests.

    Only `get_book(id)` is exercised; everything else is a no-op so the
    highlight service can call its real methods without a backing Calibre
    metadata.db (which is not available in the unit-test environment).
    """

    def __init__(self, books: dict[int, dict]):
        self._books = books

    def get_book(self, book_id: int) -> dict | None:
        return self._books.get(book_id)


@pytest.fixture
def fake_calibre(monkeypatch):
    """Patch `get_calibre_db` so the export tests see a fake catalog.

    Defaults to two books (id 1 and 2). Per-test overrides possible.
    """
    fake = _FakeCalibreDB(
        books={
            1: {"title": "Test Book", "authors": "Jane Doe"},
            2: {"title": "Second Book", "authors": "John Smith"},
        }
    )
    monkeypatch.setattr(calibre_db_module, "get_calibre_db", lambda: fake)
    # Also patch where the highlights service imported it from.
    from alejandria.services import highlights as highlights_module
    monkeypatch.setattr(highlights_module, "get_calibre_db", lambda: fake)
    return fake


def _create_highlight(
    client: TestClient,
    cookies: dict,
    book_id: int,
    text: str = "highlighted passage",
    cfi: str = "epubcfi(/6/4!/4/2,/1:0,/1:1)",
    note: str | None = None,
    color: str = "#FFEB3B",
) -> dict:
    payload: dict = {
        "book_id": book_id,
        "cfi": cfi,
        "text": text,
        "color": color,
    }
    if note is not None:
        payload["note"] = note
    r = client.post(
        "/api/highlights",
        json=payload,
        cookies=cookies,
        headers={"X-CSRF-Token": cookies.get("alejandria_csrf", "")},
    )
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# H1 + H2 + H3: PATCH note + color, 403 vs 404, hex validator
# ---------------------------------------------------------------------------


def test_patch_highlight_note_and_color(client: TestClient, auth_cookies, auth_headers):
    """H1 + H2: PATCH note and color together; both round-trip through the API."""
    h = _create_highlight(client, auth_cookies, book_id=1, text="x", cfi="a")
    r = client.patch(
        f"/api/highlights/{h['id']}",
        json={"note": "important passage", "color": "#81C784"},
        cookies=auth_cookies,
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["note"] == "important passage"
    assert body["color"] == "#81C784"


def test_patch_highlight_other_user_forbidden(
    client: TestClient, auth_cookies, auth_headers, second_user
):
    """H3: another user's highlight returns 403 (not 404)."""
    h = _create_highlight(client, auth_cookies, book_id=1, text="x", cfi="a")
    second_headers = {"X-CSRF-Token": second_user.get("alejandria_csrf", "")}
    r = client.patch(
        f"/api/highlights/{h['id']}",
        json={"color": "#64B5F6"},
        cookies=second_user,
        headers=second_headers,
    )
    assert r.status_code == 403, r.text


def test_patch_highlight_missing_404(client: TestClient, auth_cookies, auth_headers):
    """H3: missing highlight id returns 404."""
    r = client.patch(
        "/api/highlights/99999",
        json={"color": "#FFEB3B"},
        cookies=auth_cookies,
        headers=auth_headers,
    )
    assert r.status_code == 404, r.text


def test_patch_highlight_bad_color_422(
    client: TestClient, auth_cookies, auth_headers
):
    """H2: legacy named color token is rejected by the schema validator."""
    h = _create_highlight(client, auth_cookies, book_id=1, text="x", cfi="a")
    r = client.patch(
        f"/api/highlights/{h['id']}",
        json={"color": "yellow"},
        cookies=auth_cookies,
        headers=auth_headers,
    )
    assert r.status_code == 422, r.text


def test_patch_highlight_clear_note(
    client: TestClient, auth_cookies, auth_headers
):
    """H1: setting note back to null clears it on the row."""
    h = _create_highlight(
        client, auth_cookies, book_id=1, text="x", cfi="a", note="first"
    )
    assert h["note"] == "first"
    r = client.patch(
        f"/api/highlights/{h['id']}",
        json={"note": None},
        cookies=auth_cookies,
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["note"] is None


def test_delete_highlight_other_user_forbidden(
    client: TestClient, auth_cookies, auth_headers, second_user
):
    """H3: delete also returns 403 when the row is not yours (not 404)."""
    h = _create_highlight(client, auth_cookies, book_id=1, text="x", cfi="a")
    second_headers = {"X-CSRF-Token": second_user.get("alejandria_csrf", "")}
    r = client.delete(
        f"/api/highlights/{h['id']}",
        cookies=second_user,
        headers=second_headers,
    )
    assert r.status_code == 403, r.text


# ---------------------------------------------------------------------------
# H7: export per-book and zip
# ---------------------------------------------------------------------------


def test_export_markdown_per_book(
    client: TestClient, auth_cookies, fake_calibre
):
    """H7: per-book export returns a markdown document with H1 + quotes."""
    _create_highlight(
        client, auth_cookies, book_id=1, text="alpha", cfi="a", note="first"
    )
    _create_highlight(
        client, auth_cookies, book_id=1, text="beta", cfi="b", note="second"
    )
    r = client.get(
        "/api/highlights/export?format=markdown&book_id=1",
        cookies=auth_cookies,
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/markdown")
    body = r.text
    # Header should include "# " for the H1
    assert "# " in body
    # Both highlights should be present
    assert "alpha" in body
    assert "beta" in body


def test_export_markdown_missing_book_404(
    client: TestClient, auth_cookies, fake_calibre
):
    """H7: a book_id that doesn't exist returns 404."""
    r = client.get(
        "/api/highlights/export?format=markdown&book_id=99999",
        cookies=auth_cookies,
    )
    assert r.status_code == 404, r.text


def test_export_markdown_zip(client: TestClient, auth_cookies, fake_calibre):
    """H7: no book_id returns a zip with one .md per book the user has highlighted."""
    _create_highlight(client, auth_cookies, book_id=1, text="a", cfi="a")
    _create_highlight(client, auth_cookies, book_id=2, text="b", cfi="b")
    r = client.get(
        "/api/highlights/export?format=markdown",
        cookies=auth_cookies,
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/zip"
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = z.namelist()
    # Two books → at least two entries. None of them is the README.
    assert any(n.endswith(".md") for n in names)
    assert "README.md" not in names


def test_export_markdown_zip_empty(
    client: TestClient, auth_cookies, fake_calibre
):
    """H7: zero highlights → 200 with a zip containing only README.md."""
    # Delete any pre-existing highlights (from earlier tests in this file)
    # so this test is order-independent.
    existing = client.get("/api/highlights", cookies=auth_cookies).json()
    for h in existing:
        client.delete(
            f"/api/highlights/{h['id']}",
            cookies=auth_cookies,
            headers={"X-CSRF-Token": auth_cookies.get("alejandria_csrf", "")},
        )
    r = client.get(
        "/api/highlights/export?format=markdown",
        cookies=auth_cookies,
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/zip"
    z = zipfile.ZipFile(io.BytesIO(r.content))
    assert "README.md" in z.namelist()


def test_export_requires_auth(client: TestClient):
    """H7: export endpoint requires authentication."""
    r = client.get(
        "/api/highlights/export?format=markdown&book_id=1"
    )
    assert r.status_code == 401, r.text
