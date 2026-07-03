from pathlib import Path
from typing import TYPE_CHECKING

from zrb.config.web_auth_config import WebAuthConfig
from zrb.util.file import read_file

if TYPE_CHECKING:
    # We want fastapi to only be loaded when necessary to decrease footprint
    from fastapi import FastAPI


def serve_static_resources(app: "FastAPI", web_auth_config: WebAuthConfig) -> None:
    # lazy: heavy third-party
    from fastapi.responses import PlainTextResponse
    from fastapi.staticfiles import StaticFiles

    _STATIC_DIR = Path(__file__).parent / "resources"

    # StaticFiles fully owns /static (with built-in path containment). A custom
    # {file_path:path} handler here would be shadowed by the mount today and
    # become a path-traversal hole the day route registration is reordered.
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    @app.get("/refresh-token.js", include_in_schema=False)
    async def refresh_token_js():
        return PlainTextResponse(
            content=_get_refresh_token_js(
                60 * web_auth_config.access_token_expire_minutes / 3
            ),
            media_type="application/javascript",
        )


def _get_refresh_token_js(refresh_interval_seconds: float):
    return read_file(
        str(Path(__file__).parent / "refresh-token.template.js"),
        {"refreshIntervalSeconds": f"{refresh_interval_seconds}"},
    )
