import pytest
from asgi_lifespan import LifespanManager
from httpx import AsyncClient
from src.main import app


@pytest.fixture()
async def test_client_generator(scope="module"):
    async with LifespanManager(app):
        async with AsyncClient(app=app, base_url="http://localhost") as ac:
            yield ac
