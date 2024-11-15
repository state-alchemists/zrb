import httpx

from ....schema.user import NewUserData, UserData
from .base_client import BaseClient


class ApiClient(BaseClient):

    def __init__(self, base_url: str):
        self.base_url = base_url

    async def create_user(self, data: NewUserData) -> UserData:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/users", params=data.model_dump()
            )
            response.raise_for_status()
            return NewUserData.model_validate(response.json())

    async def get_all_users(self) -> list[UserData]:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/api/v1/users")
            response.raise_for_status()
            return [UserData.model_validate(data) for data in response.json()]
