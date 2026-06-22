"""OIDC / OAuth2 authentication flow."""

from __future__ import annotations

import secrets
from typing import Any
from urllib.parse import urlencode

import httpx

from alejandria.config import get_settings


class OIDCClient:
    """Minimal OIDC client for Authentik, Authelia, Keycloak, Pocket ID, etc."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._discovery_cache: dict[str, Any] | None = None

    @property
    def enabled(self) -> bool:
        return self.settings.oidc_enabled

    async def _discover(self) -> dict[str, Any]:
        """Fetch OIDC discovery document."""
        if self._discovery_cache:
            return self._discovery_cache
        if not self.settings.oidc_issuer:
            raise ValueError("OIDC issuer not configured")

        url = self.settings.oidc_issuer.rstrip("/") + "/.well-known/openid-configuration"
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
            r.raise_for_status()
            self._discovery_cache = r.json()
            return self._discovery_cache

    async def get_authorization_url(self, state: str, redirect_uri: str | None = None) -> str:
        """Build the OIDC authorization URL."""
        disc = await self._discover()
        params = {
            "response_type": "code",
            "client_id": self.settings.oidc_client_id,
            "redirect_uri": redirect_uri or self.settings.oidc_redirect_uri,
            "scope": "openid email profile",
            "state": state,
        }
        return f"{disc['authorization_endpoint']}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str | None = None) -> dict[str, Any]:
        """Exchange auth code for tokens."""
        disc = await self._discover()
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                disc["token_endpoint"],
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": self.settings.oidc_client_id,
                    "client_secret": self.settings.oidc_client_secret,
                    "redirect_uri": redirect_uri or self.settings.oidc_redirect_uri,
                },
            )
            r.raise_for_status()
            return r.json()

    async def get_userinfo(self, access_token: str) -> dict[str, Any]:
        """Fetch user info from OIDC provider."""
        disc = await self._discover()
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                disc["userinfo_endpoint"],
                headers={"Authorization": f"Bearer {access_token}"},
            )
            r.raise_for_status()
            return r.json()

    @staticmethod
    def generate_state() -> str:
        """Generate a random state parameter for CSRF protection."""
        return secrets.token_urlsafe(32)
