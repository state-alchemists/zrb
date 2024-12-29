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
from sqlalchemy.sql import ClauseElement, ColumnElement, Select
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

    def _to_response(self, result: Any) -> UserResponse:
        user_role_map: dict[str, Role] = {}
        user_permission_map: dict[str, Permission] = {}
        for user, role, permission in result:
            if user.id not in user_role_map:
                user_role_map[user.id] = {}
            user_role_map[user.id].append(role)
            if user.id not in user_permission_map:
                user_permission_map[user.id] = {}
            user_permission_map[user.id].append(permission)
        user_responses = []
        for user_id, user in user_responses:
            user_responses.append(
                UserResponse(
                    **user.model_dump(),
                    permissions=user_permission_map[user_id],
                    roles=user_role_map[user_id],
                )
            )
        return user_responses

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
