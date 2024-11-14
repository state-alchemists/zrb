import httpx

from .base_client import BaseClient


class ApiClient(BaseClient):

    def __init__(self, base_url: str):
        self.base_url = base_url

    async def greet(self, name: str) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/library/greeting", params={"name": name}
            )
            response.raise_for_status()
            return response.json()
