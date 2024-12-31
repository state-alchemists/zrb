from fastapi import FastAPI
from my_app_name.common.app_factory import app
from my_app_name.common.schema import BasicResponse
from my_app_name.config import APP_MAIN_MODULE, APP_MODE, APP_MODULES


def serve_route(app: FastAPI):
    if APP_MODE != "microservices" or "my_module" not in APP_MODULES:
        return
    if APP_MAIN_MODULE == "my_module":
        _serve_health_check(app)
        _serve_readiness_check(app)


def _serve_health_check(app: FastAPI):
    @app.api_route("/health", methods=["GET", "HEAD"], response_model=BasicResponse)
    async def health():
        """
        Microservice's health check
        """
        return BasicResponse(message="ok")


def _serve_readiness_check(app: FastAPI):
    @app.api_route("/readiness", methods=["GET", "HEAD"], response_model=BasicResponse)
    async def readiness():
        """
        Microservice's readiness check
        """
        return BasicResponse(message="ok")


serve_route(app)
