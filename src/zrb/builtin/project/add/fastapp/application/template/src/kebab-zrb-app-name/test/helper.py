from asgi_lifespan import LifespanManager
from httpx import AsyncClient
from src.main import app


async def init_test_client() -> AsyncClient:
    async with LifespanManager(app):
        async with AsyncClient(app=app, base_url="http://localhost") as ac:
            yield ac
