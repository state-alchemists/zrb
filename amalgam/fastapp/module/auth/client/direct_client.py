from ....schema.user import NewUserData, UserData
from ..service.user.usecase import user_usecase
from .base_client import BaseClient


class DirectClient(BaseClient):

    async def create_user(self, data: NewUserData) -> UserData:
        return await user_usecase.create_user(data)

    async def get_all_users(self) -> list[UserData]:
        return await user_usecase.get_all_users()
