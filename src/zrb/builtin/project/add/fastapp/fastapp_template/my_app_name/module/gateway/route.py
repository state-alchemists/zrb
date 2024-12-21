from fastapi import FastAPI
from my_app_name.common.app import app
from my_app_name.common.schema import BasicResponse
from my_app_name.config import APP_MAIN_MODULE, APP_MODE, APP_MODULES
from my_app_name.module.gateway.subroute.auth import serve_auth_route


def serve_health_check(app: FastAPI):
    @app.api_route("/health", methods=["GET", "HEAD"], response_model=BasicResponse)
    async def health():
        """
        My App Name's health check
        """
        return BasicResponse(message="ok")


def serve_readiness_check(app: FastAPI):
    @app.api_route("/readiness", methods=["GET", "HEAD"], response_model=BasicResponse)
    async def readiness():
        """
        My App Name's readiness check
        """
        return BasicResponse(message="ok")


def serve_route(app: FastAPI):
    if APP_MODE != "monolith" and "gateway" not in APP_MODULES:
        return
    if APP_MODE == "monolith" or APP_MAIN_MODULE == "gateway":
        serve_health_check(app)
        serve_readiness_check(app)

    # Serve Auth Route
    serve_auth_route(app)


serve_route(app)
