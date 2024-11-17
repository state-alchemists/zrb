from ...common.app import app
from ...common.schema import BasicResponse
from ...config import APP_MODE, APP_MODULES
from .service.user.usecase import user_usecase

if APP_MODE == "microservices" and "auth" in APP_MODULES:

    @app.api_route("/health", methods=["GET", "HEAD"], response_model=BasicResponse)
    async def health():
        return BasicResponse(message="ok")

    @app.api_route("/readiness", methods=["GET", "HEAD"], response_model=BasicResponse)
    async def readiness():
        return BasicResponse(message="ok")

    user_usecase.serve_route(app)
