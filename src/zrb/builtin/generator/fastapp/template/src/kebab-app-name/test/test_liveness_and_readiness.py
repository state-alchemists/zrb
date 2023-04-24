from src.config import app_name
import pytest


@pytest.mark.asyncio
async def test_liveness(test_client):
    client = await test_client
    response = await client.get("/liveness")
    assert response.status_code == 200
    assert response.json() == {'app': app_name, 'alive': True}


@pytest.mark.asyncio
async def test_readiness(test_client):
    client = await test_client
    response = await client.get("/readiness")
    assert response.status_code == 200
    assert response.json() == {'app': app_name, 'ready': True}
