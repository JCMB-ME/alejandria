"""Phase B: OIDC state persistence + role-change session kill switch."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from alejandria.auth.oidc import OIDCClient


@pytest.mark.asyncio
async def test_persist_state_roundtrip(client: TestClient):
    """Persisting then consuming a state returns True; second consume returns False.

    The ``client`` fixture forces the app lifespan to run, which calls
    ``init_db()`` (Alembic upgrade head) and ensures ``oidc_states`` exists.
    """
    from alejandria.db import SessionLocal
    from alejandria.models.oidc_state import OIDCState

    client_obj = OIDCClient()
    state = OIDCClient.generate_state()
    await client_obj.persist_state(state)

    try:
        ok = await OIDCClient.consume_state(state)
        assert ok is True
        ok2 = await OIDCClient.consume_state(state)
        assert ok2 is False  # already consumed
    finally:
        with SessionLocal() as db:
            db.execute(OIDCState.__table__.delete().where(OIDCState.state == state))
            db.commit()


@pytest.mark.asyncio
async def test_consume_unknown_state(client: TestClient):
    ok = await OIDCClient.consume_state("not-a-real-state-token")
    assert ok is False


def test_admin_disable_user_revokes_sessions(client: TestClient):
    """Disabling a user via PATCH /users/{id} deletes all their sessions."""
    # Reset the in-memory rate limit bucket so earlier tests (e.g.,
    # test_login_rate_limit_returns_429) don't make this assertion flake
    # with 429.
    from alejandria.auth import rate_limit
    rate_limit._per_minute.clear()
    rate_limit._per_hour.clear()

    # Login as admin (auto-created on first request).
    r = client.post("/api/auth/login/json",
                    json={"username": "admin", "password": "testpass"})
    assert r.status_code == 200
    admin_cookies = r.cookies
    csrf_token = admin_cookies.get("alejandria_csrf", "")
    csrf_header = {"X-CSRF-Token": csrf_token}

    # Create a target user. Pass cookies via the test client (which
    # carries them along to the next request).
    r = client.post(
        "/api/settings/users",
        json={
            "username": "victim",
            "email": "victim@example.com",
            "password": "victimpass",
            "role": "user",
        },
        headers=csrf_header,
    )
    assert r.status_code == 201, r.text
    victim_id = r.json()["id"]

    # Login as the victim (must be a separate TestClient session because
    # the in-process client would otherwise carry admin cookies).
    from fastapi.testclient import TestClient
    from alejandria.main import create_app
    with TestClient(create_app()) as victim_client:
        r = victim_client.post(
            "/api/auth/login/json",
            json={"username": "victim", "password": "victimpass"},
        )
        assert r.status_code == 200, r.text

        # Sanity: /api/auth/me works for the victim.
        me = victim_client.get("/api/auth/me")
        assert me.status_code == 200

        # Use the admin's existing client (with admin cookies still set)
        # to disable the victim.
        r = client.patch(
            f"/api/settings/users/{victim_id}",
            json={"is_active": False},
            headers=csrf_header,
        )
        assert r.status_code == 200, r.text

        # Victim's session must now be invalid.
        me2 = victim_client.get("/api/auth/me")
        assert me2.status_code == 401
