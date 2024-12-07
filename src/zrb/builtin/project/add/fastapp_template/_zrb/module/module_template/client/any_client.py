from abc import ABC, abstractmethod

from fastapp_template.schema.user import UserCreate, UserResponse, UserUpdate


class BaseClient(ABC):
    @abstractmethod
    async def get_user_by_id(self, user_id: str) -> UserResponse:
        pass

    @abstractmethod
    async def get_all_users(self) -> list[UserResponse]:
        pass

    @abstractmethod
    async def create_user(
        self, data: UserCreate | list[UserCreate]
    ) -> UserResponse | list[UserResponse]:
        pass

    @abstractmethod
    async def update_user(self, user_id: str, data: UserUpdate) -> UserResponse:
        pass

    @abstractmethod
    async def delete_user(self, user_id: str) -> UserResponse:
        pass
