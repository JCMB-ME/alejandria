"""Tests for the SSRF URL validator."""

from __future__ import annotations

import pytest

from alejandria.services.scraper.ssrf import validate_url


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://127.0.0.1:8080/api",
        "http://10.0.0.1/",
        "http://10.255.255.255/",
        "http://172.16.0.1/",
        "http://172.31.0.1/",
        "http://192.168.0.1/",
        "http://192.168.1.100/",
        "http://169.254.169.254/latest/meta-data/",
        "http://0.0.0.0/",
        "http://100.64.0.1/",
        "http://224.0.0.1/",
        "http://255.255.255.255/",
        "file:///etc/passwd",
        "ftp://example.com/file",
        "javascript:alert(1)",
        "data:text/plain,hi",
        "gopher://example.com",
        "ws://example.com/",
    ],
)
def test_rejects_private_or_unsupported(url: str):
    with pytest.raises(ValueError):
        validate_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://1.1.1.1/",
        "https://8.8.8.8/",
        "https://example.com/",
        "https://example.com/path?q=1#x",
        "https://example.com:8443/path",
    ],
)
def test_accepts_public(url: str):
    out = validate_url(url)
    assert out.startswith(("http://", "https://"))


def test_rejects_empty():
    with pytest.raises(ValueError):
        validate_url("")


def test_rejects_missing_host():
    with pytest.raises(ValueError):
        validate_url("http:///path")


def test_loopback_allowed_when_flag_set():
    # Tests use this flag so we can run an aiohttp test server locally.
    out = validate_url("http://127.0.0.1:0/", allow_loopback=True)
    assert out.startswith("http://127.0.0.1")


def test_canonical_lowercases_host():
    out = validate_url("https://Example.COM/Path")
    assert out.startswith("https://example.com")
