from abc import ABC, abstractmethod

from fastapp_template.schema.user import (
    UserCreateWithAudit,
    UserResponse,
    UserUpdateWithAudit,
)


class AnyClient(ABC):
    @abstractmethod
    async def get_user_by_id(self, user_id: str) -> UserResponse:
        pass

    @abstractmethod
    async def get_all_users(self) -> list[UserResponse]:
        pass

    @abstractmethod
    async def create_user(
        self, data: UserCreateWithAudit | list[UserCreateWithAudit]
    ) -> UserResponse | list[UserResponse]:
        pass

    @abstractmethod
    async def update_user(
        self, user_id: str, data: UserUpdateWithAudit
    ) -> UserResponse:
        pass

    @abstractmethod
    async def delete_user(self, user_id: str) -> UserResponse:
        pass
