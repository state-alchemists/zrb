from logging import Logger

from my_app_name.common.base_service import BaseService
from my_app_name.module.auth.service.role.repository.role_repository import (
    RoleRepository,
)
from my_app_name.schema.role import (
    MultipleRoleResponse,
    RoleCreateWithPermissionsAndAudit,
    RoleResponse,
    RoleUpdateWithPermissionsAndAudit,
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
    async def get_roles(
        self,
        page: int = 1,
        page_size: int = 10,
        sort: str | None = None,
        filter: str | None = None,
    ) -> MultipleRoleResponse:
        roles = await self.role_repository.get(page, page_size, filter, sort)
        count = await self.role_repository.count(filter)
        return MultipleRoleResponse(data=roles, count=count)

    @BaseService.route(
        "/api/v1/roles/bulk",
        methods=["post"],
        response_model=list[RoleResponse],
    )
    async def create_role_bulk(
        self, data: list[RoleCreateWithPermissionsAndAudit]
    ) -> list[RoleResponse]:
        permission_ids = [row.get_permission_ids() for row in data]
        data = [row.get_role_create_with_audit() for row in data]
        roles = await self.role_repository.create_bulk(data)
        if len(roles) > 0:
            created_by = roles[0].created_by
            await self.role_repository.add_permissions(
                data={role.id: permission_ids[i] for i, role in enumerate(roles)},
                created_by=created_by,
            )
        return await self.role_repository.get_by_ids([role.id for role in roles])

    @BaseService.route(
        "/api/v1/roles",
        methods=["post"],
        response_model=RoleResponse,
    )
    async def create_role(
        self, data: RoleCreateWithPermissionsAndAudit
    ) -> RoleResponse:
        permission_ids = data.get_permission_ids()
        data = data.get_role_create_with_audit()
        role = await self.role_repository.create(data)
        await self.role_repository.add_permissions(
            data={role.id: permission_ids}, created_by=role.created_by
        )
        return await self.role_repository.get_by_id(role.id)

    @BaseService.route(
        "/api/v1/roles/bulk",
        methods=["put"],
        response_model=RoleResponse,
    )
    async def update_role_bulk(
        self, role_ids: list[str], data: RoleUpdateWithPermissionsAndAudit
    ) -> RoleResponse:
        permission_ids = [row.get_permission_ids() for row in data]
        data = [row.get_role_update_with_audit() for row in data]
        roles = await self.role_repository.update_bulk(role_ids, data)
        if len(roles) > 0:
            updated_by = roles[0].updated_by
            await self.role_repository.remove_all_permissions(
                [role.id for role in roles]
            )
            await self.role_repository.add_permissions(
                data={role.id: permission_ids[i] for i, role in enumerate(roles)},
                created_by=updated_by,
            )
        return await self.role_repository.get_by_ids([role.id for role in roles])

    @BaseService.route(
        "/api/v1/roles/{role_id}",
        methods=["put"],
        response_model=RoleResponse,
    )
    async def update_role(
        self, role_id: str, data: RoleUpdateWithPermissionsAndAudit
    ) -> RoleResponse:
        permission_ids = data.get_permission_ids()
        data = data.get_role_update_with_audit()
        role = await self.role_repository.update(role_id, data)
        await self.role_repository.remove_all_permissions([role.id])
        await self.role_repository.add_permissions(
            data={role.id: permission_ids}, created_by=role.updated_by
        )
        return await self.role_repository.get_by_id(role.id)

    @BaseService.route(
        "/api/v1/roles/{role_id}",
        methods=["delete"],
        response_model=RoleResponse,
    )
    async def delete_role_bulk(
        self, role_ids: list[str], deleted_by: str
    ) -> RoleResponse:
        roles = await self.role_repository.delete_bulk(role_ids)
        return await self.role_repository.get_by_ids([role.id for role in roles])

    @BaseService.route(
        "/api/v1/roles/{role_id}",
        methods=["delete"],
        response_model=RoleResponse,
    )
    async def delete_role(self, role_id: str, deleted_by: str) -> RoleResponse:
        role = await self.role_repository.delete(role_id)
        return await self.role_repository.get_by_id(role.id)
