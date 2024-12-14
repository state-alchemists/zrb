from fastapp_template.common.app import app
from fastapp_template.common.schema import BasicResponse
from fastapp_template.config import APP_MODE, APP_MODULES
from fastapp_template.module.auth.service.user.user_usecase import user_usecase


def serve_route():
    if APP_MODE == "microservices" and (
        len(APP_MODULES) > 0 and APP_MODULES[0] == "auth"
    ):
        """
        To make sure health/readiness check is only served once,
        the following will only run if this application run as an auth microservice
        """

        @app.api_route("/health", methods=["GET", "HEAD"], response_model=BasicResponse)
        async def health():
            return BasicResponse(message="ok")

        @app.api_route(
            "/readiness", methods=["GET", "HEAD"], response_model=BasicResponse
        )
        async def readiness():
            return BasicResponse(message="ok")

    user_usecase.serve_route(app)


if APP_MODE == "monolith" or "auth" in APP_MODULES:
    """
    Will only serve route if one of these conditions is true:
    - This application run as a monolith
    - This application run as as an auth microservice
    """
    serve_route()
