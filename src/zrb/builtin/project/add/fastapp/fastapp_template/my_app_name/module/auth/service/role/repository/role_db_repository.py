import datetime
from typing import Any

import ulid
from my_app_name.common.base_db_repository import BaseDBRepository
from my_app_name.common.error import InvalidValueError
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
                role_map[role.id]["permissions"].append(permission)
        return [
            RoleResponse(
                **data["role"].model_dump(),
                permission_names=[
                    permission.name for permission in data["permissions"]
                ],
            )
            for data in role_map.values()
        ]

    async def validate_permission_names(self, permission_names: list[str]):
        async with self._session_scope() as session:
            result = await self._execute_statement(
                session,
                select(Permission.name).where(Permission.name.in_(permission_names)),
            )
            existing_permissions = {row[0] for row in result.all()}
            # Identify any missing permission names
            missing_permissions = set(permission_names) - existing_permissions
            if missing_permissions:
                raise InvalidValueError(
                    f"Permission(s) not found: {', '.join(missing_permissions)}"
                )

    async def add_permissions(self, data: dict[str, list[str]], created_by: str):
        now = datetime.datetime.now(datetime.timezone.utc)
        # get mapping from perrmission names to permission ids
        all_permission_names = {
            name for permission_names in data.values() for name in permission_names
        }
        async with self._session_scope() as session:
            result = await self._execute_statement(
                session,
                select(Permission.id, Permission.name).where(
                    Permission.name.in_(all_permission_names)
                ),
            )
            permission_mapping = {row.name: row.id for row in result}
        # Assemble data dict
        data_dict_list: list[dict[str, Any]] = []
        for role_id, permission_names in data.items():
            for permission_name in permission_names:
                data_dict_list.append(
                    self._model_to_data_dict(
                        RolePermission(
                            id=ulid.new().str,
                            role_id=role_id,
                            permission_id=permission_mapping.get(permission_name),
                            created_at=now,
                            created_by=created_by,
                        )
                    )
                )
        if len(data_dict_list) == 0:
            return
        # Insert rolePermissions
        async with self._session_scope() as session:
            await self._execute_statement(
                session, insert(RolePermission).values(data_dict_list)
            )

    async def remove_all_permissions(self, role_ids: list[str] = []):
        async with self._session_scope() as session:
            await self._execute_statement(
                session,
                delete(RolePermission).where(RolePermission.role_id.in_(role_ids)),
            )
