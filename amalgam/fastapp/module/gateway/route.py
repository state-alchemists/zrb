from config import APP_MODE, APP_MODULES
from common.app import app
from module.library.client.factory import client
from fastapi.responses import PlainTextResponse

if APP_MODE == "monolith" or "gateway" in APP_MODULES:

    @app.get("/", response_class=PlainTextResponse)
    async def read_root():
        return await client.greet("world")
