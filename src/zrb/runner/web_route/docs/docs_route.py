from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # We want fastapi to only be loaded when necessary to decrease footprint
    from fastapi import FastAPI


def serve_docs(app: "FastAPI") -> None:
    from fastapi.openapi.docs import get_swagger_ui_html

    @app.get("/docs", include_in_schema=False)
    async def swagger_ui_html():
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title="Zrb",
            swagger_favicon_url="/static/favicon-32x32.png",
        )
