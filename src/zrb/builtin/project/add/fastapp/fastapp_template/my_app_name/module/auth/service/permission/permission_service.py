from logging import Logger

from my_app_name.common.base_service import BaseService
from my_app_name.common.parser_factory import parse_filter_param, parse_sort_param
from my_app_name.module.auth.service.permission.repository.permission_repository import (
    PermissionRepository,
)
from my_app_name.schema.permission import (
    MultiplePermissionResponse,
    Permission,
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
    async def get_all_permissions(
        self,
        page: int = 1,
        page_size: int = 10,
        sort: str | None = None,
        filter: str | None = None,
    ) -> MultiplePermissionResponse:
        filters = parse_filter_param(Permission, filter) if filter else None
        sorts = parse_sort_param(Permission, sort) if sort else None
        data = await self.permission_repository.get_all(
            page=page, page_size=page_size, filters=filters, sorts=sorts
        )
        count = await self.permission_repository.count(filters=filters)
        return MultiplePermissionResponse(data=data, count=count)

    @BaseService.route(
        "/api/v1/permissions",
        methods=["post"],
        response_model=PermissionResponse | list[PermissionResponse],
    )
    async def create_permission(
        self, data: PermissionCreateWithAudit | list[PermissionCreateWithAudit]
    ) -> PermissionResponse | list[PermissionResponse]:
        if isinstance(data, PermissionCreateWithAudit):
            return await self.permission_repository.create(data)
        return await self.permission_repository.create_bulk(data)

    @BaseService.route(
        "/api/v1/permissions/{permission_id}",
        methods=["put"],
        response_model=PermissionResponse,
    )
    async def update_permission(
        self, permission_id: str, data: PermissionUpdateWithAudit
    ) -> PermissionResponse:
        return await self.permission_repository.update(permission_id, data)

    @BaseService.route(
        "/api/v1/permissions/{permission_id}",
        methods=["delete"],
        response_model=PermissionResponse,
    )
    async def delete_permission(
        self, permission_id: str, deleted_by: str
    ) -> PermissionResponse:
        return await self.permission_repository.delete(permission_id)
