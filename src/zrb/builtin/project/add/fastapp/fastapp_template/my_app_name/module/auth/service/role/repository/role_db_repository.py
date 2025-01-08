import datetime
from typing import Any

import ulid
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
from sqlmodel import delete, insert, select


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
            .join(
                Permission, Permission.id == RolePermission.permission_id, isouter=True
            )
        )

    def _rows_to_responses(self, rows: list[tuple[Any, ...]]) -> list[RoleResponse]:
        role_map: dict[str, dict[str, Any]] = {}
        role_permission_map: dict[str, list[str]] = {}
        for role, permission in rows:
            if role.id not in role_map:
                role_map[role.id] = {"role": role, "permissions": []}
                role_permission_map[role.id] = []
            if (
                permission is not None
                and permission.id not in role_permission_map[role.id]
            ):
                role_permission_map[role.id].append(permission.id)
                role_map[role.id]["permissions"].append(permission.model_dump())
        return [
            RoleResponse(**data["role"].model_dump(), permissions=data["permissions"])
            for data in role_map.values()
        ]

    async def add_permissions(self, data: dict[str, list[str]], created_by: str):
        now = datetime.datetime.now(datetime.timezone.utc)
        data_dict_list: list[dict[str, Any]] = []
        for role_id, permission_ids in data.items():
            for permission_id in permission_ids:
                data_dict_list.append(
                    self._model_to_data_dict(
                        RolePermission(
                            id=ulid.new().str,
                            role_id=role_id,
                            permission_id=permission_id,
                            created_at=now,
                            created_by=created_by,
                        )
                    )
                )
        async with self._session_scope() as session:
            await self._execute_statement(
                session, insert(RolePermission).values(data_dict_list)
            )

    async def remove_all_permissions(self, role_ids: list[str] = []):
        async with self._session_scope() as session:
            await self._execute_statement(
                session,
                delete(RolePermission).where(RolePermission.role_id._in(role_ids)),
            )
