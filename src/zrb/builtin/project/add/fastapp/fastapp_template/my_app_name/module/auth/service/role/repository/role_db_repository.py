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

    async def add_permissions(self, role_id, permission_names: list[str]) -> Role:
        # TODO: complete this
        select_statement = self._select().where(self.db_model.id == role_id)
        rows = await self._execute_select_statement(select_statement)
        responses = self._rows_to_responses(rows)
        return self._ensure_one(responses)

    async def remove_permissions(self, role_id, permission_names: list[str]) -> Role:
        # TODO: complete this
        select_statement = self._select().where(self.db_model.id == role_id)
        rows = await self._execute_select_statement(select_statement)
        responses = self._rows_to_responses(rows)
        return self._ensure_one(responses)


def _remove_create_model_additional_property(
    data: RoleCreateWithAudit,
) -> RoleCreateWithAudit:
    return RoleCreateWithAudit(
        **{key: val for key, val in data.model_dump().items() if key != "permissions"}
    )
