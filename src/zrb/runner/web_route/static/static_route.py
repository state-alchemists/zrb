import os
from typing import TYPE_CHECKING

from zrb.config.web_auth_config import WebAuthConfig
from zrb.util.file import read_file

if TYPE_CHECKING:
    # We want fastapi to only be loaded when necessary to decrease footprint
    from fastapi import FastAPI


def serve_static_resources(app: "FastAPI", web_auth_config: WebAuthConfig) -> None:
    from fastapi import HTTPException
    from fastapi.responses import FileResponse, PlainTextResponse
    from fastapi.staticfiles import StaticFiles

    _STATIC_DIR = os.path.join(os.path.dirname(__file__), "resources")

    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    # Serve static files
    @app.get("/static/{file_path:path}", include_in_schema=False)
    async def static_files(file_path: str):
        full_path = os.path.join(_STATIC_DIR, file_path)
        if os.path.isfile(full_path):
            return FileResponse(full_path)
        raise HTTPException(status_code=404, detail="File not found")

    @app.get("/refresh-token.js", include_in_schema=False)
    async def refresh_token_js():
        return PlainTextResponse(
            content=_get_refresh_token_js(
                60 * web_auth_config.access_token_expire_minutes / 3
            ),
            media_type="application/javascript",
        )


def _get_refresh_token_js(refresh_interval_seconds: int):
    _DIR = os.path.dirname(__file__)
    return read_file(
        os.path.join(_DIR, "refresh-token.template.js"),
        {"refreshIntervalSeconds": f"{refresh_interval_seconds}"},
    )
