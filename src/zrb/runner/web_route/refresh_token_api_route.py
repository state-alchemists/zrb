from typing import TYPE_CHECKING

from zrb.runner.web_config.config import WebConfig
from zrb.runner.web_schema.token import RefreshTokenRequest
from zrb.runner.web_util.cookie import set_auth_cookie
from zrb.runner.web_util.token import regenerate_tokens

if TYPE_CHECKING:
    # We want fastapi to only be loaded when necessary to decrease footprint
    from fastapi import FastAPI


def serve_refresh_token_api(app: "FastAPI", web_config: WebConfig) -> None:
    from fastapi import Cookie, Response
    from fastapi.responses import JSONResponse

    @app.post("/api/v1/refresh-token")
    async def refresh_token_api(
        response: Response,
        body: RefreshTokenRequest = None,
        refresh_token_cookie: str = Cookie(
            None, alias=web_config.refresh_token_cookie_name
        ),
    ):
        # Try to get the refresh token from the request body first
        refresh_token = body.refresh_token if body else None
        # If not in the body, try to get it from the cookie
        if not refresh_token:
            refresh_token = refresh_token_cookie
        # If we still don't have a refresh token, raise an exception
        if not refresh_token:
            return JSONResponse(
                content={"detail": "Refresh token not provided"}, status_code=401
            )
        # Get token
        new_token = regenerate_tokens(web_config, refresh_token)
        set_auth_cookie(web_config, response, new_token)
        return new_token
