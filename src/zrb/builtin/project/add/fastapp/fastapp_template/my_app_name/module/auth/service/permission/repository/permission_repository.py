from abc import ABC, abstractmethod

from my_app_name.schema.permission import (
    Permission,
    PermissionCreateWithAudit,
    PermissionResponse,
    PermissionUpdateWithAudit,
)


class PermissionRepository(ABC):
    @abstractmethod
    async def create(
        self, permission_data: PermissionCreateWithAudit
    ) -> PermissionResponse:
        pass

    @abstractmethod
    async def get_by_id(self, permission_id: str) -> PermissionResponse:
        pass

    @abstractmethod
    async def get_all(self) -> list[Permission]:
        pass

    @abstractmethod
    async def update(
        self, permission_id: str, permission_data: PermissionUpdateWithAudit
    ) -> PermissionResponse:
        pass

    @abstractmethod
    async def delete(self, permission_id: str) -> PermissionResponse:
        pass

    @abstractmethod
    async def create_bulk(
        self, permission_data_list: list[PermissionCreateWithAudit]
    ) -> list[PermissionResponse]:
        pass
