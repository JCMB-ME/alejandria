"""Application settings loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
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

    @field_validator("library_path", "config_path", "caches_path", "db_path")
    @classmethod
    def ensure_absolute(cls, v: Path) -> Path:
        """Ensure paths are absolute."""
        if str(v) == ":memory:":
            return v
        return v.resolve() if not v.is_absolute() else v

    @property
    def calibre_metadata_db(self) -> Path:
        """Path to Calibre metadata.db."""
        return self.library_path / "metadata.db"

    @property
    def calibre_bin_path(self) -> str:
        """Resolve calibre binary path."""
        if self.calibre_bin:
            return self.calibre_bin
        # Common locations
        for path in ("/opt/calibre/calibredb", "/opt/calibre/ebook-convert",
                     "/usr/bin/calibredb", "/usr/bin/ebook-convert",
                     "calibredb", "ebook-convert"):
            try:
                import shutil
                resolved = shutil.which(path) or path
                if Path(resolved).exists() if Path(resolved).is_absolute() else True:
                    return path
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
