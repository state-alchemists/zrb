from typing import Any

from my_app_name.common.base_db_repository import BaseDBRepository
from my_app_name.module.auth.service.role.repository.role_repository import (
    RoleRepository,
)
from my_app_name.schema.permission import Permission
from my_app_name.schema.role import (
    Role,
    RoleCreateWithAudit,
    RolePermission,
    RoleResponse,
    RoleUpdateWithAudit,
)
from sqlalchemy.sql import Select
from sqlmodel import select


class RoleDBRepository(
    BaseDBRepository[
        Role,
        RoleResponse,
        RoleCreateWithAudit,
        RoleUpdateWithAudit,
    ],
    RoleRepository,
):
    db_model = Role
    response_model = RoleResponse
    create_model = RoleCreateWithAudit
    update_model = RoleUpdateWithAudit
    entity_name = "role"

    def _select(self) -> Select:
        return (
            select(Role, Permission)
            .join(RolePermission, RolePermission.role_id == Role.id, isouter=True)
            .join(Permission, Permission.id == RolePermission.role_id, isouter=True)
        )

    def _rows_to_responses(self, rows: list[tuple[Role, Permission]]) -> RoleResponse:
        role_map: dict[str, dict[str, Any]] = {}
        for role, permission in rows:
            if role.id not in role_map:
                role_map[role.id] = {"role": role, "permissions": set()}
            if permission:
                role_map[role.id]["permissions"].add(permission)
        return [
            RoleResponse(
                **data["role"].model_dump(), permissions=list(data["permissions"])
            )
            for data in role_map.values()
        ]

    async def create(self, data: RoleCreateWithAudit) -> RoleResponse:
        permission_names = data.permissions if data.permissions else []
        # Insert role
        data = _remove_create_model_additional_property(data)
        new_role = await self._create(data)
        select_statement = self._select().where(self.db_model.id == new_role.id)
        rows = await self._execute_select_statement(select_statement)
        # Create role permissions
        # TODO: work on this
        responses = self._rows_to_responses(rows)
        return self._ensure_one(responses)

    async def create_bulk(self, data_list: list[RoleCreateWithAudit]) -> list[Role]:
        permission_names_list = [data.permission_names for data in data_list]
        # Insert roles
        data_list = [
            _remove_create_model_additional_property(data) for data in data_list
        ]
        db_instances = await self._create_bulk(data_list)
        select_statement = self._select().where(
            self.db_model.id.in_([instance.id for instance in db_instances])
        )
        rows = await self._execute_select_statement(select_statement)
        # Create role permissions
        # TODO worn this
        responses = self._rows_to_responses(rows)
        return responses


def _remove_create_model_additional_property(
    data: RoleCreateWithAudit,
) -> RoleCreateWithAudit:
    return RoleCreateWithAudit(
        **{key: val for key, val in data.model_dump().items() if key != "permissions"}
    )
