import datetime
from typing import Any

import ulid
from my_app_name.common.base_db_repository import BaseDBRepository
from my_app_name.module.auth.service.user.repository.user_repository import (
    UserRepository,
)
from my_app_name.schema.permission import Permission
from my_app_name.schema.role import Role, RolePermission
from my_app_name.schema.user import (
    User,
    UserCreateWithAudit,
    UserResponse,
    UserRole,
    UserUpdateWithAudit,
)
from passlib.context import CryptContext
from sqlalchemy.sql import Select
from sqlmodel import delete, insert, select

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


class UserDBRepository(
    BaseDBRepository[User, UserResponse, UserCreateWithAudit, UserUpdateWithAudit],
    UserRepository,
):
    db_model = User
    response_model = UserResponse
    create_model = UserCreateWithAudit
    update_model = UserUpdateWithAudit
    entity_name = "user"
    column_preprocessors = {"password": hash_password}

    def _select(self) -> Select:
        return (
            select(User, Role, Permission)
            .join(UserRole, UserRole.user_id == User.id, isouter=True)
            .join(Role, Role.id == UserRole.role_id, isouter=True)
            .join(RolePermission, RolePermission.role_id == Role.id, isouter=True)
            .join(
                Permission, Permission.id == RolePermission.permission_id, isouter=True
            )
        )

    def _rows_to_responses(
        self, rows: list[tuple[User, Role, Permission]]
    ) -> UserResponse:
        user_map: dict[str, dict[str, Any]] = {}
        user_role_map: dict[str, list[str]] = {}
        user_permission_map: dict[str, list[str]] = {}
        for user, role, permission in rows:
            if user.id not in user_map:
                user_map[user.id] = {"user": user, "roles": [], "permissions": []}
                user_role_map[user.id] = []
                user_permission_map[user.id] = []
            if role is not None and role.id not in user_role_map[user.id]:
                user_role_map[user.id].append(role.id)
                user_map[user.id]["roles"].append(role.model_dump())
            if (
                permission is not None
                and permission.id not in user_permission_map[user.id]
            ):
                user_permission_map[user.id].append(permission.id)
                user_map[user.id]["permissions"].append(permission.model_dump())
        return [
            UserResponse(
                **data["user"].model_dump(),
                roles=list(data["roles"]),
                permissions=list(data["permissions"])
            )
            for data in user_map.values()
        ]

    async def add_roles(self, data: dict[str, list[str]], created_by: str) -> User:
        now = datetime.datetime.now(datetime.timezone.utc)
        data_dict_list: list[dict[str, Any]] = []
        for user_id, role_ids in data.items():
            for role_id in role_ids:
                data_dict_list.append(
                    self._model_to_data_dict(
                        UserRole(
                            id=ulid.new().str,
                            user_id=user_id,
                            role_id=role_id,
                            created_at=now,
                            created_by=created_by,
                        )
                    )
                )
        async with self._session_scope() as session:
            await self._execute_statement(
                session, insert(UserRole).values(data_dict_list)
            )

    async def remove_all_roles(self, user_ids: list[str] = []) -> User:
        async with self._session_scope() as session:
            await self._execute_statement(
                session,
                delete(UserRole).where(UserRole.user_id._in(user_ids)),
            )

    async def get_by_credentials(self, username: str, password: str) -> UserResponse:
        select_statement = self._select().where(
            User.username == username, User.password == hash_password(password)
        )
        rows = await self._execute_select_statement(select_statement)
        responses = self._rows_to_responses(rows)
        return self._ensure_one(responses)
