from fastapi import FastAPI
from my_app_name.common.app_factory import app
from my_app_name.common.schema import BasicResponse
from my_app_name.config import APP_MAIN_MODULE, APP_MODE, APP_MODULES
from my_app_name.module.auth.service.permission.permission_service_factory import (
    permission_service,
)
from my_app_name.module.auth.service.user.user_service_factory import user_service


def serve_health_check(app: FastAPI):
    @app.api_route("/health", methods=["GET", "HEAD"], response_model=BasicResponse)
    async def health():
        """
        Microservice's health check
        """
        return BasicResponse(message="ok")


def serve_readiness_check(app: FastAPI):
    @app.api_route("/readiness", methods=["GET", "HEAD"], response_model=BasicResponse)
    async def readiness():
        """
        Microservice's readiness check
        """
        return BasicResponse(message="ok")


def serve_route(app: FastAPI):
    if APP_MODE != "microservices" or "auth" not in APP_MODULES:
        return
    if APP_MAIN_MODULE == "auth":
        serve_health_check(app)
        serve_readiness_check(app)

    # Serve user endpoints for APIClient
    user_service.serve_route(app)
    permission_service.serve_route(app)


serve_route(app)
