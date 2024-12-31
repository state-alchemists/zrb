import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import HTMLResponse
from my_app_name.common.app_factory import app
from my_app_name.common.schema import BasicResponse
from my_app_name.config import (
    APP_GATEWAY_VIEW_PATH,
    APP_MAIN_MODULE,
    APP_MODE,
    APP_MODULES,
)
from my_app_name.module.gateway.subroute.auth import serve_auth_route
from my_app_name.module.gateway.util.view import render, render_error


def serve_route(app: FastAPI):
    if APP_MODE != "monolith" and "gateway" not in APP_MODULES:
        return
    if APP_MODE == "monolith" or APP_MAIN_MODULE == "gateway":
        _serve_health_check(app)
        _serve_readiness_check(app)
        _serve_homepage(app)
        _handle_404(app)

    # Serve auth routes
    serve_auth_route(app)


def _serve_homepage(app: FastAPI):
    @app.get("/", include_in_schema=False)
    def home_page():
        return render(
            view_path=os.path.join(APP_GATEWAY_VIEW_PATH, "content", "homepage.html")
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
        return render_error(error_message="Not found", status_code=404)


serve_route(app)
