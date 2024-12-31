from abc import ABC, abstractmethod

from my_app_name.schema.permission import (
    MultiplePermissionResponse,
    PermissionCreateWithAudit,
    PermissionResponse,
    PermissionUpdateWithAudit,
)
from my_app_name.schema.role import (
    MultipleRoleResponse,
    RoleCreateWithAudit,
    RoleResponse,
    RoleUpdateWithAudit,
)
from my_app_name.schema.user import (
    MultipleUserResponse,
    UserCreateWithAudit,
    UserResponse,
    UserUpdateWithAudit,
)


class AnyClient(ABC):

    # Permission related methods

    @abstractmethod
    async def get_permission_by_id(self, permission_id: str) -> PermissionResponse:
        pass

    @abstractmethod
    async def get_all_permissions(
        self,
        page: int = 1,
        page_size: int = 10,
        sort: str | None = None,
        filter: str | None = None,
    ) -> MultiplePermissionResponse:
        pass

    @abstractmethod
    async def create_permission(
        self, data: PermissionCreateWithAudit | list[PermissionCreateWithAudit]
    ) -> PermissionResponse | list[PermissionResponse]:
        pass

    @abstractmethod
    async def update_permission(
        self, permission_id: str, data: PermissionUpdateWithAudit
    ) -> PermissionResponse:
        pass

    @abstractmethod
    async def delete_permission(self, permission_id: str) -> PermissionResponse:
        pass

    # Role related methods

    @abstractmethod
    async def get_role_by_id(self, role_id: str) -> RoleResponse:
        pass

    @abstractmethod
    async def get_all_roles(
        self,
        page: int = 1,
        page_size: int = 10,
        sort: str | None = None,
        filter: str | None = None,
    ) -> MultipleRoleResponse:
        pass

    @abstractmethod
    async def create_role(
        self, data: RoleCreateWithAudit | list[RoleCreateWithAudit]
    ) -> RoleResponse | list[RoleResponse]:
        pass

    @abstractmethod
    async def update_role(
        self, role_id: str, data: RoleUpdateWithAudit
    ) -> RoleResponse:
        pass

    @abstractmethod
    async def delete_role(self, role_id: str) -> RoleResponse:
        pass

    # User related methods

    @abstractmethod
    async def get_user_by_id(self, user_id: str) -> UserResponse:
        pass

    @abstractmethod
    async def get_all_users(
        self,
        page: int = 1,
        page_size: int = 10,
        sort: str | None = None,
        filter: str | None = None,
    ) -> MultipleUserResponse:
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
