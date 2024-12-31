from abc import ABC, abstractmethod

from my_app_name.schema.role import (
    Role,
    RoleCreateWithAudit,
    RoleResponse,
    RoleUpdateWithAudit,
)


class RoleRepository(ABC):
    @abstractmethod
    async def create(self, role_data: RoleCreateWithAudit) -> RoleResponse:
        pass

    @abstractmethod
    async def get_by_id(self, role_id: str) -> RoleResponse:
        pass

    @abstractmethod
    async def get_all(self) -> list[Role]:
        pass

    @abstractmethod
    async def update(
        self, role_id: str, role_data: RoleUpdateWithAudit
    ) -> RoleResponse:
        pass

    @abstractmethod
    async def delete(self, role_id: str) -> RoleResponse:
        pass

    @abstractmethod
    async def create_bulk(
        self, role_data_list: list[RoleCreateWithAudit]
    ) -> list[RoleResponse]:
        pass
