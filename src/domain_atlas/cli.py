"""Command-line entry point for local development."""

from __future__ import annotations

import uvicorn


def main() -> None:
    """Run the local Domain Atlas development server."""
    uvicorn.run(
        "domain_atlas.web.app:create_app",
        factory=True,
        host="127.0.0.1",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
