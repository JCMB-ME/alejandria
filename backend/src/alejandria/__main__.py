"""CLI entrypoint for Alejandría server."""

import uvicorn

from alejandria.config import get_settings


def main() -> None:
    """Run the FastAPI server."""
    settings = get_settings()
    uvicorn.run(
        "alejandria.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        reload=settings.dev_mode,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
