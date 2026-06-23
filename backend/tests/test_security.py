"""Security/auth utility tests."""

import pytest
from fastapi.testclient import TestClient

from alejandria.auth.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_token,
    hash_token,
    generate_csrf_token,
)


def test_password_hash_and_verify():
    h = hash_password("mysecretpassword")
    assert h != "mysecretpassword"
    assert verify_password("mysecretpassword", h)
    assert not verify_password("wrong", h)


def test_jwt_round_trip():
    token = create_access_token(42, extra_claims={"role": "admin"})
    payload = decode_token(token)
    assert payload["sub"] == "42"
    assert payload["role"] == "admin"


def test_hash_token_deterministic():
    assert hash_token("abc") == hash_token("abc")
    assert hash_token("abc") != hash_token("xyz")


def test_csrf_token_unique():
    tokens = {generate_csrf_token() for _ in range(100)}
    assert len(tokens) == 100


def test_settings_rejects_default_secret(monkeypatch):
    """Default secret value is rejected at validation time."""
    from pydantic import ValidationError
    from alejandria.config import Settings

    # Save and clear the override so the validator runs.
    monkeypatch.setenv("ALEJANDRIA_SECRET_KEY", "change-me-in-production-please")
    monkeypatch.delenv("ALEJANDRIA_ALLOW_INSECURE_DEFAULTS", raising=False)
    with pytest.raises(ValidationError) as ei:
        Settings(_env_file=None)  # bypass .env
    assert "well-known default" in str(ei.value)


def test_settings_rejects_short_secret(monkeypatch):
    """Secret shorter than 32 chars is rejected."""
    from pydantic import ValidationError
    from alejandria.config import Settings

    monkeypatch.setenv("ALEJANDRIA_SECRET_KEY", "short")
    monkeypatch.delenv("ALEJANDRIA_ALLOW_INSECURE_DEFAULTS", raising=False)
    with pytest.raises(ValidationError) as ei:
        Settings(_env_file=None)
    assert "too short" in str(ei.value)


def test_settings_rejects_default_password(monkeypatch):
    """Default admin password is rejected."""
    from pydantic import ValidationError
    from alejandria.config import Settings

    monkeypatch.setenv("ALEJANDRIA_ADMIN_PASSWORD", "changeme")
    monkeypatch.delenv("ALEJANDRIA_ALLOW_INSECURE_DEFAULTS", raising=False)
    with pytest.raises(ValidationError) as ei:
        Settings(_env_file=None)
    assert "well-known default" in str(ei.value)


def test_settings_escape_hatch(monkeypatch):
    """ALEJANDRIA_ALLOW_INSECURE_DEFAULTS=true bypasses validators."""
    from alejandria.config import Settings

    monkeypatch.setenv("ALEJANDRIA_SECRET_KEY", "x")
    monkeypatch.setenv("ALEJANDRIA_ALLOW_INSECURE_DEFAULTS", "true")
    s = Settings(_env_file=None)
    assert s.secret_key == "x"  # accepted with warning logged


def test_csrf_missing_token_rejected(client: TestClient):
    """A POST without the X-CSRF-Token header is rejected with 403."""
    r = client.post("/api/auth/logout")
    assert r.status_code == 403
    assert "CSRF" in r.json()["detail"]


def test_csrf_mismatched_token_rejected(client: TestClient):
    """A POST with a wrong X-CSRF-Token is rejected with 403."""
    r = client.post(
        "/api/auth/logout",
        headers={"X-CSRF-Token": "wrong-token", "Cookie": "alejandria_csrf=some-other-token"},
    )
    assert r.status_code == 403


def test_csrf_login_is_exempt(client: TestClient):
    """Login does not require a CSRF token (no session exists yet)."""
    # Reset the in-memory rate limit bucket so earlier tests don't make
    # this assertion flake with 429.
    from alejandria.auth import rate_limit
    rate_limit._per_minute.clear()
    rate_limit._per_hour.clear()
    r = client.post("/api/auth/login/json",
                    json={"username": "admin", "password": "testpass"})
    assert r.status_code in (200, 401)  # not 403

