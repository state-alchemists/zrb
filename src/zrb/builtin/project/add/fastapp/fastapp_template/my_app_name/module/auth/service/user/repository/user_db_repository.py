from typing import Any

from my_app_name.common.base_db_repository import BaseDBRepository
from my_app_name.common.error import NotFoundError
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
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select
from sqlmodel import Session, select

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

    def _get_default_select(self) -> Select:
        return (
            select(User, Role, Permission)
            .join(UserRole, UserRole.user_id == User.id, isouter=True)
            .join(Role, Role.id == UserRole.role_id, isouter=True)
            .join(RolePermission, RolePermission.role_id == Role.id, isouter=True)
            .join(Permission, Permission.id == RolePermission.role_id, isouter=True)
        )

    def _rows_to_responses(self, rows: list[Any]) -> UserResponse:
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
        statement = self._get_default_select().where(User.username == username)
        # Execute statement
        if self.is_async:
            async with AsyncSession(self.engine) as session:
                result = await session.execute(statement)
                row = result.scalar_one_or_none()
        else:
            with Session(self.engine) as session:
                result = session.exec(statement)
                row = result.scalar_one_or_none()
        # Return response
        return self._row_to_response(row)
