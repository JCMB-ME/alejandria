"""Application settings loaded from environment variables."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="ALEJANDRIA_",
        extra="ignore",
        case_sensitive=False,
    )

    # Server
    host: str = "0.0.0.0"
    port: int = 8080
    base_url: str = "http://localhost:8080"
    dev_mode: bool = False

    # Security
    secret_key: str = "change-me-in-production-please"
    allow_insecure_defaults: bool = False  # ALEJANDRIA_ALLOW_INSECURE_DEFAULTS
    cookie_secure: bool = True  # ALEJANDRIA_COOKIE_SECURE; set false for HTTP dev
    opds_require_auth: bool = True  # ALEJANDRIA_OPDS_REQUIRE_AUTH
    session_lifetime: int = 60 * 60 * 24 * 30  # 30 days
    jwt_algorithm: str = "HS256"
    jwt_audience: str = "alejandria"

    # Initial admin
    admin_username: str = "admin"
    admin_password: str = "changeme"
    admin_email: str = "admin@example.com"

    # Paths
    library_path: Path = Path("/library")
    config_path: Path = Path("/config")
    caches_path: Path = Path("/config/caches")
    db_path: Path = Path("/config/alejandria.db")
    static_path: Path = Path("/app/frontend/build")

    # Calibre
    enable_calibre: bool = True
    calibre_bin: str = ""  # Auto-detect if empty

    # SMTP / Kindle
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_use_tls: bool = True
    kindle_emails: str = ""  # Comma-separated

    # OIDC
    oidc_enabled: bool = False
    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_redirect_uri: str = ""

    # Logging
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "console"

    # Misc
    timezone: str = "UTC"

    # Conversion cap
    convert_max_concurrent: int = 2  # ALEJANDRIA_CONVERT_MAX_CONCURRENT

    # Web scraper
    scraper_enabled: bool = True
    scraper_output_dir: Path = Path("/config/scrapes")
    scraper_max_concurrent_jobs: int = 2
    scraper_image_concurrency: int = 4
    scraper_max_pages_per_job: int = 2000
    scraper_default_delay_ms: int = 100
    scraper_max_total_size_mb: int = 500
    scraper_browser_headless: bool = True
    scraper_adapters_file: Path = Path("/config/site-adapters.yaml")
    scraper_proxy: str = ""
    scraper_user_agent: str = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    scraper_max_jobs_per_hour: int = 10

    @field_validator(
        "library_path",
        "config_path",
        "caches_path",
        "db_path",
        "scraper_output_dir",
        "scraper_adapters_file",
    )
    @classmethod
    def ensure_absolute(cls, v: Path) -> Path:
        """Ensure paths are absolute."""
        if str(v) == ":memory:":
            return v
        return v.resolve() if not v.is_absolute() else v

    _DEFAULT_SECRET_VALUES: ClassVar[frozenset[str]] = frozenset({
        "change-me-in-production-please",
        "change-me-to-a-long-random-string",
        "changeme",
        "",
    })
    _DEFAULT_PASSWORD_VALUES: ClassVar[frozenset[str]] = frozenset({"changeme", ""})

    @field_validator("secret_key", mode="after")
    @classmethod
    def _validate_secret_key(cls, v: str) -> str:
        # Allow tests / dev to opt out with the escape hatch.
        if os.environ.get("ALEJANDRIA_ALLOW_INSECURE_DEFAULTS", "").lower() in (
            "1", "true", "yes"
        ):
            import structlog
            structlog.get_logger(__name__).warning(
                "insecure_defaults_override_active",
                hint="ALEJANDRIA_ALLOW_INSECURE_DEFAULTS=true is set; do not run this in production.",
            )
            return v
        if v in cls._DEFAULT_SECRET_VALUES:
            raise ValueError(
                "ALEJANDRIA_SECRET_KEY is set to a well-known default. "
                "Generate a new one with: "
                "python -c 'import secrets; print(secrets.token_urlsafe(64))' "
                "and set it in .env. To override this check for local dev only, "
                "set ALEJANDRIA_ALLOW_INSECURE_DEFAULTS=true."
            )
        if len(v) < 32:
            raise ValueError(
                f"ALEJANDRIA_SECRET_KEY is too short ({len(v)} chars). "
                "Use at least 32 characters of high-entropy random data."
            )
        return v

    @field_validator("admin_password", mode="after")
    @classmethod
    def _validate_admin_password(cls, v: str) -> str:
        if os.environ.get("ALEJANDRIA_ALLOW_INSECURE_DEFAULTS", "").lower() in (
            "1", "true", "yes"
        ):
            return v
        if v in cls._DEFAULT_PASSWORD_VALUES:
            raise ValueError(
                "ALEJANDRIA_ADMIN_PASSWORD is set to a well-known default. "
                "Change it to a strong password (>= 8 chars) and set it in .env. "
                "To override this check for local dev only, "
                "set ALEJANDRIA_ALLOW_INSECURE_DEFAULTS=true."
            )
        if len(v) < 8:
            raise ValueError(
                f"ALEJANDRIA_ADMIN_PASSWORD is too short ({len(v)} chars). "
                "Use at least 8 characters."
            )
        return v

    @property
    def calibre_metadata_db(self) -> Path:
        """Path to Calibre metadata.db."""
        return self.library_path / "metadata.db"

    @property
    def calibre_bin_path(self) -> str:
        """Resolve calibre binary path."""
        if self.calibre_bin:
            return self.calibre_bin
        # Common locations — Linux, macOS (Docker), and Windows native.
        candidates = (
            "/opt/calibre/calibredb",
            "/opt/calibre/ebook-convert",
            "/usr/bin/calibredb",
            "/usr/bin/ebook-convert",
            "C:/Program Files/Calibre2/calibredb.exe",
            "C:/Program Files/Calibre2/ebook-convert.exe",
            "C:/Program Files/calibre/calibredb.exe",
            "C:/Program Files/calibre/ebook-convert.exe",
            "calibredb",
            "ebook-convert",
        )
        import shutil

        for path in candidates:
            try:
                if Path(path).is_absolute():
                    if Path(path).exists():
                        return path
                else:
                    resolved = shutil.which(path)
                    if resolved:
                        return resolved
            except Exception:
                continue
        return "calibredb"

    @property
    def parsed_kindle_emails(self) -> list[str]:
        """Parse Kindle email list."""
        return [e.strip() for e in self.kindle_emails.split(",") if e.strip()]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
