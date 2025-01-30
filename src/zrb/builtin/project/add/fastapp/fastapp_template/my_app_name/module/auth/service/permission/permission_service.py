from logging import Logger

from my_app_name.common.base_service import BaseService
from my_app_name.module.auth.service.permission.repository.permission_repository import (
    PermissionRepository,
)
from my_app_name.schema.permission import (
    MultiplePermissionResponse,
    PermissionCreateWithAudit,
    PermissionResponse,
    PermissionUpdateWithAudit,
)


class PermissionService(BaseService):

    def __init__(self, logger: Logger, permission_repository: PermissionRepository):
        super().__init__(logger)
        self.permission_repository = permission_repository

    @BaseService.route(
        "/api/v1/permissions/{permission_id}",
        methods=["get"],
        response_model=PermissionResponse,
    )
    async def get_permission_by_id(self, permission_id: str) -> PermissionResponse:
        return await self.permission_repository.get_by_id(permission_id)

    @BaseService.route(
        "/api/v1/permissions",
        methods=["get"],
        response_model=MultiplePermissionResponse,
    )
    async def get_permissions(
        self,
        page: int = 1,
        page_size: int = 10,
        sort: str | None = None,
        filter: str | None = None,
    ) -> MultiplePermissionResponse:
        permissions = await self.permission_repository.get(
            page, page_size, filter, sort
        )
        count = await self.permission_repository.count(filter)
        return MultiplePermissionResponse(data=permissions, count=count)

    @BaseService.route(
        "/api/v1/permissions/bulk",
        methods=["post"],
        response_model=list[PermissionResponse],
    )
    async def create_permission_bulk(
        self, data: list[PermissionCreateWithAudit]
    ) -> list[PermissionResponse]:
        permissions = await self.permission_repository.create_bulk(data)
        return await self.permission_repository.get_by_ids(
            [permission.id for permission in permissions]
        )

    @BaseService.route(
        "/api/v1/permissions",
        methods=["post"],
        response_model=PermissionResponse,
    )
    async def create_permission(
        self, data: PermissionCreateWithAudit
    ) -> PermissionResponse:
        permission = await self.permission_repository.create(data)
        return await self.permission_repository.get_by_id(permission.id)

    @BaseService.route(
        "/api/v1/permissions/bulk",
        methods=["put"],
        response_model=list[PermissionResponse],
    )
    async def update_permission_bulk(
        self, permission_ids: list[str], data: PermissionUpdateWithAudit
    ) -> list[PermissionResponse]:
        await self.permission_repository.update_bulk(permission_ids, data)
        return await self.permission_repository.get_by_ids(permission_ids)

    @BaseService.route(
        "/api/v1/permissions/{permission_id}",
        methods=["put"],
        response_model=PermissionResponse,
    )
    async def update_permission(
        self, permission_id: str, data: PermissionUpdateWithAudit
    ) -> PermissionResponse:
        await self.permission_repository.update(permission_id, data)
        return await self.permission_repository.get_by_id(permission_id)

    @BaseService.route(
        "/api/v1/permissions/bulk",
        methods=["delete"],
        response_model=list[PermissionResponse],
    )
    async def delete_permission_bulk(
        self, permission_ids: list[str], deleted_by: str
    ) -> list[PermissionResponse]:
        permissions = await self.permission_repository.get_by_ids(permission_ids)
        await self.permission_repository.delete_bulk(permission_ids)
        return permissions

    @BaseService.route(
        "/api/v1/permissions/{permission_id}",
        methods=["delete"],
        response_model=PermissionResponse,
    )
    async def delete_permission(
        self, permission_id: str, deleted_by: str
    ) -> PermissionResponse:
        permission = await self.permission_repository.get_by_id(permission_id)
        await self.permission_repository.delete(permission_id)
        return permission
