from fastapp_template.common.app import app
from fastapp_template.common.schema import BasicResponse
from fastapp_template.config import APP_MODE, APP_MODULES


def serve_route():
    if APP_MODE == "microservices" and (
        len(APP_MODULES) > 0 and APP_MODULES[0] == "my_module"
    ):
        """
        To make sure health/readiness check is only served once,
        the following will only run if this application run as a my_module microservice
        """

        @app.api_route("/health", methods=["GET", "HEAD"], response_model=BasicResponse)
        async def health():
            return BasicResponse(message="ok")

        @app.api_route(
            "/readiness", methods=["GET", "HEAD"], response_model=BasicResponse
        )
        async def readiness():
            return BasicResponse(message="ok")


if APP_MODE == "monolith" or "my_module" in APP_MODULES:
    """
    Will only serve route if one of these conditions is true:
    - This application run as a monolith
    - This application run as as a my_module microservice
    """
    serve_route()
