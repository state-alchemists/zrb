from typing import Any

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
from sqlmodel import select

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
            .join(Permission, Permission.id == RolePermission.role_id, isouter=True)
        )

    def _rows_to_responses(
        self, rows: list[tuple[User, Role, Permission]]
    ) -> UserResponse:
        user_map: dict[str, dict[str, Any]] = {}
        for user, role, permission in rows:
            if user.id not in user_map:
                user_map[user.id] = {"user": user, "roles": set(), "permissions": set()}
            if role:
                user_map[user.id]["roles"].add(role)
            if permission:
                user_map[user.id]["permissions"].add(permission)
        return [
            UserResponse(
                **data["user"].model_dump(),
                roles=list(data["roles"]),
                permissions=list(data["permissions"])
            )
            for data in user_map.values()
        ]

    async def get_by_credentials(self, username: str, password: str) -> UserResponse:
        select_statement = self._select().where(
            User.username == username, User.password == hash_password(password)
        )
        rows = await self._execute_select_statement(select_statement)
        responses = self._rows_to_responses(rows)
        return self._ensure_one(responses)
