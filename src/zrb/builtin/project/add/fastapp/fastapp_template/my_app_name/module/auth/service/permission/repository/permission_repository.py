from abc import ABC, abstractmethod

from my_app_name.schema.permission import (
    Permission,
    PermissionCreateWithAudit,
    PermissionResponse,
    PermissionUpdateWithAudit,
)


class PermissionRepository(ABC):

    @abstractmethod
    async def get_by_id(self, id: str) -> PermissionResponse:
        """Get permission by id"""

    @abstractmethod
    async def get_by_ids(self, id_list: list[str]) -> PermissionResponse:
        """Get permissions by ids"""

    @abstractmethod
    async def get(
        self,
        page: int = 1,
        page_size: int = 10,
        filter: str | None = None,
        sort: str | None = None,
    ) -> list[Permission]:
        """Get permissions by filter and sort"""

    @abstractmethod
    async def count(self, filter: str | None = None) -> int:
        """Count permissions by filter"""

    @abstractmethod
    async def create(self, data: PermissionCreateWithAudit) -> Permission:
        """Create a new permission"""

    @abstractmethod
    async def create_bulk(
        self, data: list[PermissionCreateWithAudit]
    ) -> list[Permission]:
        """Create some permissions"""

    @abstractmethod
    async def delete(self, id: str) -> Permission:
        """Delete a permission"""

    @abstractmethod
    async def delete_bulk(self, id_list: list[str]) -> list[Permission]:
        """Delete some permissions"""

    @abstractmethod
    async def update(self, id: str, data: PermissionUpdateWithAudit) -> Permission:
        """Update a permission"""

    @abstractmethod
    async def update_bulk(
        self, id_list: list[str], data: PermissionUpdateWithAudit
    ) -> list[Permission]:
        """Update some permissions"""
