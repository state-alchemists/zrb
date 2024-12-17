from abc import ABC, abstractmethod

from my_app_name.schema.user import (
    User,
    UserCreateWithAudit,
    UserResponse,
    UserUpdateWithAudit,
)


class UserRepository(ABC):
    @abstractmethod
    async def create(self, user_data: UserCreateWithAudit) -> UserResponse:
        pass

    @abstractmethod
    async def get_by_id(self, user_id: str) -> UserResponse:
        pass

    @abstractmethod
    async def get_all(self) -> list[User]:
        pass

    @abstractmethod
    async def update(
        self, user_id: str, user_data: UserUpdateWithAudit
    ) -> UserResponse:
        pass

    @abstractmethod
    async def delete(self, user_id: str) -> UserResponse:
        pass

    @abstractmethod
    async def create_bulk(
        self, user_data_list: list[UserCreateWithAudit]
    ) -> list[UserResponse]:
        pass

    @abstractmethod
    async def get_by_credentials(self, username: str, password: str) -> UserResponse:
        pass
