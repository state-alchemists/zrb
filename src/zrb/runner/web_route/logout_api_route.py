from typing import TYPE_CHECKING

from zrb.runner.web_config.config import WebConfig

if TYPE_CHECKING:
    # We want fastapi to only be loaded when necessary to decrease footprint
    from fastapi import FastAPI


def serve_logout_api(app: "FastAPI", web_config: WebConfig) -> None:
    from fastapi import Response

    @app.get("/api/v1/logout")
    @app.post("/api/v1/logout")
    async def logout_api(response: Response):
        response.delete_cookie(web_config.access_token_cookie_name)
        response.delete_cookie(web_config.refresh_token_cookie_name)
        return {"message": "Logout successful"}
