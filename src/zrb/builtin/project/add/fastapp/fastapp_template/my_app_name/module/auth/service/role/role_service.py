from logging import Logger

from my_app_name.common.base_service import BaseService
from my_app_name.common.parser_factory import parse_filter_param, parse_sort_param
from my_app_name.module.auth.service.role.repository.role_repository import (
    RoleRepository,
)
from my_app_name.schema.role import (
    MultipleRoleResponse,
    Role,
    RoleCreateWithAudit,
    RoleResponse,
    RoleUpdateWithAudit,
)


class RoleService(BaseService):
    def __init__(self, logger: Logger, role_repository: RoleRepository):
        super().__init__(logger)
        self.role_repository = role_repository

    @BaseService.route(
        "/api/v1/roles/{role_id}",
        methods=["get"],
        response_model=RoleResponse,
    )
    async def get_role_by_id(self, role_id: str) -> RoleResponse:
        return await self.role_repository.get_by_id(role_id)

    @BaseService.route(
        "/api/v1/roles",
        methods=["get"],
        response_model=MultipleRoleResponse,
    )
    async def get_all_roles(
        self,
        page: int = 1,
        page_size: int = 10,
        sort: str | None = None,
        filter: str | None = None,
    ) -> MultipleRoleResponse:
        filters = parse_filter_param(Role, filter) if filter else None
        sorts = parse_sort_param(Role, sort) if sort else None
        data = await self.role_repository.get_all(
            page=page, page_size=page_size, filters=filters, sorts=sorts
        )
        count = await self.role_repository.count(filters=filters)
        return MultipleRoleResponse(data=data, count=count)

    @BaseService.route(
        "/api/v1/roles",
        methods=["post"],
        response_model=RoleResponse | list[RoleResponse],
    )
    async def create_role(
        self, data: RoleCreateWithAudit | list[RoleCreateWithAudit]
    ) -> RoleResponse | list[RoleResponse]:
        if isinstance(data, RoleCreateWithAudit):
            return await self.role_repository.create(data)
        return await self.role_repository.create_bulk(data)

    @BaseService.route(
        "/api/v1/roles/{role_id}",
        methods=["put"],
        response_model=RoleResponse,
    )
    async def update_role(
        self, role_id: str, data: RoleUpdateWithAudit
    ) -> RoleResponse:
        return await self.role_repository.update(role_id, data)

    @BaseService.route(
        "/api/v1/roles/{role_id}",
        methods=["delete"],
        response_model=RoleResponse,
    )
    async def delete_role(self, role_id: str, deleted_by: str) -> RoleResponse:
        return await self.role_repository.delete(role_id)
