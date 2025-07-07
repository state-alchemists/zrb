from typing import TYPE_CHECKING, Annotated

from zrb.config.web_auth_config import WebAuthConfig
from zrb.runner.web_util.cookie import set_auth_cookie
from zrb.runner.web_util.token import generate_tokens_by_credentials

if TYPE_CHECKING:
    # We want fastapi to only be loaded when necessary to decrease footprint
    from fastapi import FastAPI


def serve_login_api(app: "FastAPI", web_auth_config: WebAuthConfig) -> None:
    from fastapi import Depends, Response
    from fastapi.responses import JSONResponse
    from fastapi.security import OAuth2PasswordRequestForm

    @app.post("/api/v1/login")
    async def login_api(
        response: Response, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
    ):
        token = generate_tokens_by_credentials(
            web_auth_config=web_auth_config,
            username=form_data.username,
            password=form_data.password,
        )
        if token is None:
            return JSONResponse(
                content={"detail": "Incorrect username or password"}, status_code=400
            )
        set_auth_cookie(web_auth_config, response, token)
        return token
