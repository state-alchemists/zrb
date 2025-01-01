from abc import ABC, abstractmethod

from my_app_name.schema.user import (
    User,
    UserCreateWithAudit,
    UserResponse,
    UserUpdateWithAudit,
)


class UserRepository(ABC):

    @abstractmethod
    async def get_by_id(self, id: str) -> UserResponse:
        """Get user by id"""

    @abstractmethod
    async def get_by_ids(self, id_list: list[str]) -> UserResponse:
        """Get users by ids"""

    @abstractmethod
    async def get(
        self,
        page: int = 1,
        page_size: int = 10,
        filter: str | None = None,
        sort: str | None = None,
    ) -> list[User]:
        """Get users by filter and sort"""

    @abstractmethod
    async def count(self, filter: str | None = None) -> int:
        """Count users by filter"""

    @abstractmethod
    async def create(self, data: UserCreateWithAudit) -> User:
        """Create a new user"""

    @abstractmethod
    async def create_bulk(self, data: list[UserCreateWithAudit]) -> list[User]:
        """Create some users"""

    @abstractmethod
    async def delete(self, id: str) -> User:
        """Delete a user"""

    @abstractmethod
    async def delete_bulk(self, id_list: list[str]) -> list[User]:
        """Delete some users"""

    @abstractmethod
    async def update(self, id: str, data: UserUpdateWithAudit) -> User:
        """Update a user"""

    @abstractmethod
    async def update_bulk(
        self, id_list: list[str], data: UserUpdateWithAudit
    ) -> list[User]:
        """Update some users"""

    @abstractmethod
    async def get_by_credentials(self, username: str, password: str) -> UserResponse:
        """Get user by credential"""
