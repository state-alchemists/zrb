from fastapp_template.common.app import app
from fastapp_template.common.schema import BasicResponse
from fastapp_template.config import APP_MODE, APP_MODULES
from fastapp_template.module.auth.service.user.user_usecase import user_usecase

if APP_MODE == "microservices" and "auth" in APP_MODULES:

    if APP_MODE == "microservices" and (
        len(APP_MODULES) > 0 and APP_MODULES[0] == "auth"
    ):

        @app.api_route("/health", methods=["GET", "HEAD"], response_model=BasicResponse)
        async def health():
            return BasicResponse(message="ok")

        @app.api_route(
            "/readiness", methods=["GET", "HEAD"], response_model=BasicResponse
        )
        async def readiness():
            return BasicResponse(message="ok")

    user_usecase.serve_route(app)
