from fastapi.responses import PlainTextResponse

from ...common.app import app
from ...config import APP_MODE, APP_MODULES
from ..auth.client.factory import client

if APP_MODE == "monolith" or "gateway" in APP_MODULES:

    @app.get("/", response_class=PlainTextResponse)
    async def read_root():
        return await client.greet("world")
