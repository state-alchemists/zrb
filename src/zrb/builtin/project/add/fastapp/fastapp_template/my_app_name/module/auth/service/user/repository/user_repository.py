from abc import ABC, abstractmethod

from my_app_name.schema.user import (
    User,
    UserCreateWithAudit,
    UserResponse,
    UserSessionResponse,
    UserTokenData,
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
    async def validate_role_names(self, role_names: list[str]):
        """Validate Role names"""

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
    async def get_active_user_sessions(self, user_id: str) -> list[UserSessionResponse]:
        """Get user sessions"""

    @abstractmethod
    async def get_user_session_by_access_token(
        self, access_token: str
    ) -> UserSessionResponse:
        """Get user session by access token"""

    @abstractmethod
    async def get_user_session_by_refresh_token(
        self, refresh_token: str
    ) -> UserSessionResponse:
        """Get user session by refresh token"""

    @abstractmethod
    async def create_user_session(
        self, user_id: str, token_data: UserTokenData
    ) -> UserSessionResponse:
        """Create new user session"""

    @abstractmethod
    async def update_user_session(
        self, user_id: str, session_id: str, token_data: UserTokenData
    ) -> UserSessionResponse:
        """Update user session"""

    @abstractmethod
    async def delete_expired_user_sessions(self, user_id: str):
        """Delete expired user sessions"""

    @abstractmethod
    async def delete_user_sessions(self, session_ids: list[str]):
        """Delete user session"""
