from fastapi import FastAPI
from fastapp_template.common.app import app
from fastapp_template.common.schema import BasicResponse
from fastapp_template.config import APP_MAIN_MODULE, APP_MODE, APP_MODULES


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
    if APP_MODE != "microservices" or "my_module" not in APP_MODULES:
        return
    if APP_MAIN_MODULE == "my_module":
        serve_health_check(app)
        serve_readiness_check(app)


serve_route(app)
