from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import HTMLResponse, RedirectResponse
from my_app_name.common.app_factory import app
from my_app_name.common.schema import BasicResponse
from my_app_name.config import (
    APP_AUTH_ACCESS_TOKEN_COOKIE_NAME,
    APP_MAIN_MODULE,
    APP_MODE,
    APP_MODULES,
)
from my_app_name.module.auth.client.auth_client_factory import auth_client
from my_app_name.module.gateway.subroute.auth import serve_auth_route
from my_app_name.module.gateway.util.auth import get_current_user
from my_app_name.module.gateway.util.view import render_content, render_error
from my_app_name.schema.user import AuthUserResponse


def serve_route(app: FastAPI):
    if APP_MODE != "monolith" and "gateway" not in APP_MODULES:
        return
    if APP_MODE == "monolith" or APP_MAIN_MODULE == "gateway":
        _serve_health_check(app)
        _serve_readiness_check(app)
        _serve_common_pages(app)
        _handle_404(app)

    # Serve auth routes
    serve_auth_route(app)


def _serve_common_pages(app: FastAPI):
    @app.get("/", include_in_schema=False)
    def home_page(
        current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
    ):
        return render_content(
            view_path="homepage.html",
            current_user=current_user,
            page_name="gateway.home",
        )

    @app.get("/login", include_in_schema=False)
    def login_page(
        current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
    ):
        if not current_user.is_guest:
            return RedirectResponse("/")
        return render_content(
            view_path="login.html",
            current_user=current_user,
            page_name="gateway.home",
            partials={"show_user_info": False},
        )

    @app.get("/logout", include_in_schema=False)
    def logout_page(
        current_user: Annotated[AuthUserResponse, Depends(get_current_user)],
    ):
        if current_user is None:
            return RedirectResponse("/")
        return render_content(
            view_path="logout.html",
            current_user=current_user,
            page_name="gateway.home",
            partials={"show_user_info": False},
        )


def _serve_health_check(app: FastAPI):
    @app.api_route("/health", methods=["GET", "HEAD"], response_model=BasicResponse)
    async def health():
        """
        My App Name's health check
        """
        return BasicResponse(message="ok")


def _serve_readiness_check(app: FastAPI):
    @app.api_route("/readiness", methods=["GET", "HEAD"], response_model=BasicResponse)
    async def readiness():
        """
        My App Name's readiness check
        """
        return BasicResponse(message="ok")


def _handle_404(app: FastAPI):
    @app.exception_handler(404)
    async def default_404(request: Request, exc: HTTPException) -> HTMLResponse:
        if request.url.path.startswith("/api"):
            # Re-raise the exception to let FastAPI handle it
            return await http_exception_handler(request, exc)
        # Get current user by cookies
        current_user = None
        cookie_access_token = request.cookies.get(APP_AUTH_ACCESS_TOKEN_COOKIE_NAME)
        if cookie_access_token is not None and cookie_access_token != "":
            current_user = await auth_client.get_current_user(cookie_access_token)
        # Show error page
        return render_error(
            error_message="Not found", status_code=404, current_user=current_user
        )


serve_route(app)
