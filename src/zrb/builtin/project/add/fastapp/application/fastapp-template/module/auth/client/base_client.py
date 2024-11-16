from abc import ABC, abstractmethod

from ....schema.user import NewUserData, UpdateUserData, UserData


class BaseClient(ABC):
    @abstractmethod
    async def get_user_by_id(self, user_id: str) -> UserData:
        pass

    @abstractmethod
    async def get_all_users(self) -> list[UserData]:
        pass

    @abstractmethod
    async def create_user(
        self, data: NewUserData | list[NewUserData]
    ) -> UserData | list[UserData]:
        pass

    @abstractmethod
    async def update_user(self, user_id: str, data: UpdateUserData) -> UserData:
        pass

    @abstractmethod
    async def delete_user(self, user_id: str) -> UserData:
        pass
