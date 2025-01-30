from abc import ABC, abstractmethod

from my_app_name.schema.permission import (
    MultiplePermissionResponse,
    PermissionCreateWithAudit,
    PermissionResponse,
    PermissionUpdateWithAudit,
)
from my_app_name.schema.role import (
    MultipleRoleResponse,
    RoleCreateWithPermissionsAndAudit,
    RoleResponse,
    RoleUpdateWithPermissionsAndAudit,
)
from my_app_name.schema.user import (
    AuthUserResponse,
    MultipleUserResponse,
    UserCreateWithRolesAndAudit,
    UserCredentials,
    UserResponse,
    UserSessionResponse,
    UserUpdateWithRolesAndAudit,
)


class AuthClient(ABC):

    @abstractmethod
    async def get_current_user(self, access_token: str) -> AuthUserResponse:
        """Get current user based on access token"""

    @abstractmethod
    async def create_user_session(
        self, credential: UserCredentials
    ) -> UserSessionResponse:
        """Create new user session"""

    @abstractmethod
    async def update_user_session(self, refresh_token: str) -> UserSessionResponse:
        """Update user session"""

    @abstractmethod
    async def delete_user_session(self, refresh_token: str) -> UserSessionResponse:
        """Delete user session"""

    # Permission related methods

    @abstractmethod
    async def get_permission_by_id(self, permission_id: str) -> PermissionResponse:
        """Get permission by id"""

    @abstractmethod
    async def get_permissions(
        self,
        page: int = 1,
        page_size: int = 10,
        sort: str | None = None,
        filter: str | None = None,
    ) -> MultiplePermissionResponse:
        """Get permissions by filter and sort"""

    @abstractmethod
    async def create_permission_bulk(
        self, data: list[PermissionCreateWithAudit]
    ) -> list[PermissionResponse]:
        """Create new permissions"""

    @abstractmethod
    async def create_permission(
        self, data: PermissionCreateWithAudit
    ) -> PermissionResponse:
        """Create a new permission"""

    @abstractmethod
    async def update_permission_bulk(
        self, permission_ids: list[str], data: PermissionUpdateWithAudit
    ) -> PermissionResponse:
        """Update some permissions"""

    @abstractmethod
    async def update_permission(
        self, permission_id: str, data: PermissionUpdateWithAudit
    ) -> PermissionResponse:
        """Update a permission"""

    @abstractmethod
    async def delete_permission_bulk(
        self, permission_ids: str, deleted_by: str
    ) -> PermissionResponse:
        """Delete some permissions"""

    @abstractmethod
    async def delete_permission(
        self, permission_id: str, deleted_by: str
    ) -> PermissionResponse:
        """Delete a permission"""

    # Role related methods

    @abstractmethod
    async def get_role_by_id(self, role_id: str) -> RoleResponse:
        """Get role by id"""

    @abstractmethod
    async def get_roles(
        self,
        page: int = 1,
        page_size: int = 10,
        sort: str | None = None,
        filter: str | None = None,
    ) -> MultipleRoleResponse:
        """Get roles by filter and sort"""

    @abstractmethod
    async def create_role_bulk(
        self, data: list[RoleCreateWithPermissionsAndAudit]
    ) -> list[RoleResponse]:
        """Create new roles"""

    @abstractmethod
    async def create_role(
        self, data: RoleCreateWithPermissionsAndAudit
    ) -> RoleResponse:
        """Create a new role"""

    @abstractmethod
    async def update_role_bulk(
        self, role_ids: list[str], data: RoleUpdateWithPermissionsAndAudit
    ) -> RoleResponse:
        """Update some roles"""

    @abstractmethod
    async def update_role(
        self, role_id: str, data: RoleUpdateWithPermissionsAndAudit
    ) -> RoleResponse:
        """Update a role"""

    @abstractmethod
    async def delete_role_bulk(self, role_ids: str, deleted_by: str) -> RoleResponse:
        """Delete some roles"""

    @abstractmethod
    async def delete_role(self, role_id: str, deleted_by: str) -> RoleResponse:
        """Delete a role"""

    # User related methods

    @abstractmethod
    async def get_user_by_id(self, user_id: str) -> UserResponse:
        """Get user by id"""

    @abstractmethod
    async def get_users(
        self,
        page: int = 1,
        page_size: int = 10,
        sort: str | None = None,
        filter: str | None = None,
    ) -> MultipleUserResponse:
        """Get users by filter and sort"""

    @abstractmethod
    async def create_user_bulk(
        self, data: list[UserCreateWithRolesAndAudit]
    ) -> list[UserResponse]:
        """Create new users"""

    @abstractmethod
    async def create_user(self, data: UserCreateWithRolesAndAudit) -> UserResponse:
        """Create a new user"""

    @abstractmethod
    async def update_user_bulk(
        self, user_ids: list[str], data: UserUpdateWithRolesAndAudit
    ) -> UserResponse:
        """Update some users"""

    @abstractmethod
    async def update_user(
        self, user_id: str, data: UserUpdateWithRolesAndAudit
    ) -> UserResponse:
        """Update a user"""

    @abstractmethod
    async def delete_user_bulk(self, user_ids: str, deleted_by: str) -> UserResponse:
        """Delete some users"""

    @abstractmethod
    async def delete_user(self, user_id: str, deleted_by: str) -> UserResponse:
        """Delete a user"""
