from abc import ABC, abstractmethod

from my_app_name.schema.session import SessionResponse
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
    async def add_roles(self, data: dict[str, list[str]], created_by: str):
        """Add roles to user"""

    @abstractmethod
    async def remove_all_roles(self, user_ids: list[str] = []):
        """Remove roles from user"""

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

    @abstractmethod
    async def get_by_token(self, token: str) -> UserResponse:
        """Get user by token"""

    @abstractmethod
    async def add_token(self, user_id: str, token: str):
        """Add token to user"""

    @abstractmethod
    async def remove_token(self, user_id: str, token: str):
        """Remove token from user"""

    @abstractmethod
    async def get_sessions(self, user_id: str) -> list[SessionResponse]:
        """Get sessions"""

    @abstractmethod
    async def remove_session(self, user_id: str, session_id: str) -> SessionResponse:
        """Remove a session"""
