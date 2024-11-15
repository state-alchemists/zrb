from abc import ABC, abstractmethod

from ......schema.user import NewUserData, UpdateUserData, UserData


class UserRepository(ABC):

    @abstractmethod
    async def create_user(self, new_user_data: NewUserData) -> UserData:
        pass

    @abstractmethod
    async def get_user_by_id(self, user_id: str) -> UserData | None:
        pass

    @abstractmethod
    async def get_all_users(self) -> list[UserData]:
        pass

    @abstractmethod
    async def update_user(
        self, user_id: str, update_user_data: UpdateUserData
    ) -> UserData | None:
        pass

    @abstractmethod
    async def delete_user(self, user_id: str) -> None:
        pass

    @abstractmethod
    async def create_users_bulk(
        self, new_users_data: list[NewUserData]
    ) -> list[UserData]:
        pass

    @abstractmethod
    async def get_user_by_username(self, username: str) -> UserData | None:
        pass
