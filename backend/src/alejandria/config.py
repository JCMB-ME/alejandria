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

    # Web scraper
    scraper_enabled: bool = True
    scraper_output_dir: Path = Path("/config/scrapes")
    scraper_max_concurrent_jobs: int = 2
    scraper_max_pages_per_job: int = 2000
    scraper_default_delay_ms: int = 500
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
