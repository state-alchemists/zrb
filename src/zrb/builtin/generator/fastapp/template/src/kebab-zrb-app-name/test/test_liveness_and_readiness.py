from typing import AsyncIterator

import pytest
from httpx import AsyncClient
from src.config import zrb_app_name


@pytest.mark.asyncio
async def test_get_liveness(test_client_generator: AsyncIterator[AsyncClient]):
    async for client in test_client_generator:
        response = await client.get("/liveness")
        assert response.status_code == 200
        assert response.json() == {"app": zrb_app_name, "alive": True}


@pytest.mark.asyncio
async def test_head_liveness(test_client_generator: AsyncIterator[AsyncClient]):
    async for client in test_client_generator:
        response = await client.head("/liveness")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_readiness(test_client_generator: AsyncIterator[AsyncClient]):
    async for client in test_client_generator:
        response = await client.get("/readiness")
        assert response.status_code == 200
        assert response.json() == {"app": zrb_app_name, "ready": True}


@pytest.mark.asyncio
async def test_head_readiness(test_client_generator: AsyncIterator[AsyncClient]):
    async for client in test_client_generator:
        response = await client.head("/readiness")
        assert response.status_code == 200
