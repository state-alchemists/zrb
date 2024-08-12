from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from src.config import APP_NAME


@pytest.mark.asyncio
async def test_get_liveness(test_client_generator: AsyncIterator[AsyncClient]):
    async for client in test_client_generator:
        response = await client.get("/liveness")
        assert response.status_code == 200
        assert response.json() == {"app": APP_NAME, "alive": True}


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
        assert response.json() == {"app": APP_NAME, "ready": True}


@pytest.mark.asyncio
async def test_head_readiness(test_client_generator: AsyncIterator[AsyncClient]):
    async for client in test_client_generator:
        response = await client.head("/readiness")
        assert response.status_code == 200
