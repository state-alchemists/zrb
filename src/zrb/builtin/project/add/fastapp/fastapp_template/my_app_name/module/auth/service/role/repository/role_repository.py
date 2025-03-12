from abc import ABC, abstractmethod

from my_app_name.schema.role import (
    Role,
    RoleCreateWithAudit,
    RoleResponse,
    RoleUpdateWithAudit,
)


class RoleRepository(ABC):

    @abstractmethod
    async def get_by_id(self, id: str) -> RoleResponse:
        """Get role by id"""

    @abstractmethod
    async def get_by_ids(self, id_list: list[str]) -> RoleResponse:
        """Get roles by ids"""

    @abstractmethod
    async def validate_permission_names(self, permission_names: list[str]):
        """Validate Permission names"""

    @abstractmethod
    async def add_permissions(self, data: dict[str, list[str]], created_by: str):
        """Adding permissions to roles"""

    @abstractmethod
    async def remove_all_permissions(self, role_ids: list[str] = []):
        """Remove permissions from roles"""

    @abstractmethod
    async def get(
        self,
        page: int = 1,
        page_size: int = 10,
        filter: str | None = None,
        sort: str | None = None,
    ) -> list[Role]:
        """Get roles by filter and sort"""

    @abstractmethod
    async def count(self, filter: str | None = None) -> int:
        """Count roles by filter"""

    @abstractmethod
    async def create(self, data: RoleCreateWithAudit) -> Role:
        """Create a new role"""

    @abstractmethod
    async def create_bulk(self, data: list[RoleCreateWithAudit]) -> list[Role]:
        """Create some roles"""

    @abstractmethod
    async def delete(self, id: str) -> Role:
        """Delete a role"""

    @abstractmethod
    async def delete_bulk(self, id_list: list[str]) -> list[Role]:
        """Delete some roles"""

    @abstractmethod
    async def update(self, id: str, data: RoleUpdateWithAudit) -> Role:
        """Update a role"""

    @abstractmethod
    async def update_bulk(
        self, id_list: list[str], data: RoleUpdateWithAudit
    ) -> list[Role]:
        """Update some roles"""
