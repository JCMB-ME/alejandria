"""Security/auth utility tests."""

import pytest

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
