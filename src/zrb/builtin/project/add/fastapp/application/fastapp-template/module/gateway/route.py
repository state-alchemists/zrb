from fastapi.responses import PlainTextResponse

from ...common.app import app
from ...common.schema import BasicResponse
from ...config import APP_MODE, APP_MODULES
from ..auth.client.factory import client as auth_client

if APP_MODE == "monolith" or "gateway" in APP_MODULES:

    @app.api_route("/health", methods=["GET", "HEAD"], response_class=BasicResponse)
    async def health():
        return BasicResponse(message="ok")

    @app.api_route("/readiness", methods=["GET", "HEAD"], response_class=BasicResponse)
    async def readiness():
        return BasicResponse(message="ok")

    @app.get("/", response_class=PlainTextResponse)
    async def read_root():
        return await auth_client.greet("world")
