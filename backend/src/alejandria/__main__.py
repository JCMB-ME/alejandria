"""CLI entrypoint for Alejandría server."""

import uvicorn
from dotenv import load_dotenv

from alejandria.config import get_settings


def main() -> None:
    """Run the FastAPI server."""
    # Load .env from the repo root when running outside Docker. Inside the
    # container the entrypoint already exports the same vars, so this is a
    # no-op there. Without it, ALEJANDRIA_STATIC_PATH and friends fall back
    # to the in-container defaults and the SPA cannot be served.
    load_dotenv("../.env", override=False)
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
