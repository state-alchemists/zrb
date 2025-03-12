import datetime
from typing import Any

import ulid
from my_app_name.common.base_db_repository import BaseDBRepository
from my_app_name.common.error import InvalidValueError, NotFoundError, UnauthorizedError
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
    UserSession,
    UserSessionResponse,
    UserTokenData,
    UserUpdateWithAudit,
)
from passlib.context import CryptContext
from sqlalchemy.sql import Select
from sqlmodel import delete, insert, select, update

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies if a password matches the stored hash."""
    return pwd_context.verify(plain_password, hashed_password)


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

    def _rows_to_responses(self, rows: list[tuple[Any, ...]]) -> list[UserResponse]:
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
                user_map[user.id]["roles"].append(role)
            if (
                permission is not None
                and permission.id not in user_permission_map[user.id]
            ):
                user_permission_map[user.id].append(permission.id)
                user_map[user.id]["permissions"].append(permission)
        return [
            UserResponse(
                **data["user"].model_dump(),
                role_names=[role.name for role in data["roles"]],
                permission_names=[
                    permission.name for permission in data["permissions"]
                ],
            )
            for data in user_map.values()
        ]

    async def validate_role_names(self, role_names: list[str]):
        async with self._session_scope() as session:
            result = await self._execute_statement(
                session, select(Role.name).where(Role.name.in_(role_names))
            )
            existing_roles = {row[0] for row in result.all()}
            # Identify any missing role names
            missing_roles = set(role_names) - existing_roles
            if missing_roles:
                raise InvalidValueError(
                    f"Role(s) not found: {', '.join(missing_roles)}"
                )

    async def add_roles(self, data: dict[str, list[str]], created_by: str):
        now = datetime.datetime.now(datetime.timezone.utc)
        # get mapping from role names to role ids
        all_role_names = {name for role_names in data.values() for name in role_names}
        async with self._session_scope() as session:
            result = await self._execute_statement(
                session, select(Role.id, Role.name).where(Role.name.in_(all_role_names))
            )
            role_mapping = {row.name: row.id for row in result}
        # Assemble data dict
        data_dict_list: list[dict[str, Any]] = []
        for user_id, role_names in data.items():
            for role_name in role_names:
                data_dict_list.append(
                    self._model_to_data_dict(
                        UserRole(
                            id=ulid.new().str,
                            user_id=user_id,
                            role_id=role_mapping.get(role_name),
                            created_at=now,
                            created_by=created_by,
                        )
                    )
                )
        if len(data_dict_list) == 0:
            return
        async with self._session_scope() as session:
            await self._execute_statement(
                session, insert(UserRole).values(data_dict_list)
            )

    async def remove_all_roles(self, user_ids: list[str] = []):
        async with self._session_scope() as session:
            await self._execute_statement(
                session,
                delete(UserRole).where(UserRole.user_id.in_(user_ids)),
            )

    async def get_by_credentials(self, username: str, password: str) -> UserResponse:
        async with self._session_scope() as session:
            result = await self._execute_statement(
                session, select(User).where(User.username == username, User.active)
            )
            user = result.scalar_one_or_none()
            if user is None or not verify_password(password, user.password):
                raise UnauthorizedError("Invalid username or password")
            return await self.get_by_id(user.id)

    async def delete_expired_user_sessions(self, user_id: str):
        now = datetime.datetime.now(datetime.timezone.utc)
        async with self._session_scope() as session:
            await self._execute_statement(
                session,
                delete(UserSession).where(
                    UserSession.user_id == user_id,
                    UserSession.refresh_token_expired_at < now,
                ),
            )

    async def get_active_user_sessions(self, user_id: str) -> list[UserSessionResponse]:
        now = datetime.datetime.now(datetime.timezone.utc)
        async with self._session_scope() as session:
            result = await self._execute_statement(
                session,
                select(UserSession).where(
                    UserSession.user_id == user_id,
                    UserSession.refresh_token_expired_at > now,
                ),
            )
            return [self._user_session_to_response(row[0]) for row in result.all()]

    async def get_user_session_by_access_token(
        self, access_token: str
    ) -> UserSessionResponse:
        now = datetime.datetime.now(datetime.timezone.utc)
        async with self._session_scope() as session:
            result = await self._execute_statement(
                session,
                select(UserSession).where(
                    UserSession.access_token == access_token,
                    UserSession.access_token_expired_at > now,
                ),
            )
            user_session = result.scalar_one_or_none()
            if user_session is None:
                raise NotFoundError("User session not found")
            return self._user_session_to_response(user_session)

    async def get_user_session_by_refresh_token(
        self, refresh_token: str
    ) -> UserSessionResponse:
        now = datetime.datetime.now(datetime.timezone.utc)
        async with self._session_scope() as session:
            result = await self._execute_statement(
                session,
                select(UserSession).where(
                    UserSession.refresh_token == refresh_token,
                    UserSession.refresh_token_expired_at > now,
                ),
            )
            user_session = result.scalar_one_or_none()
            if user_session is None:
                raise NotFoundError("User session not found")
            return self._user_session_to_response(user_session)

    async def create_user_session(
        self, user_id: str, token_data: UserTokenData
    ) -> UserSessionResponse:
        data_dict = self._model_to_data_dict(
            token_data, user_id=user_id, id=ulid.new().str
        )
        async with self._session_scope() as session:
            await self._execute_statement(
                session, insert(UserSession).values(**data_dict)
            )
            result = await self._execute_statement(
                session, select(UserSession).where(UserSession.id == data_dict["id"])
            )
            user_session = result.scalar_one_or_none()
            if user_session is None:
                raise NotFoundError("User session not found after created")
            return self._user_session_to_response(user_session)

    async def update_user_session(
        self, user_id: str, session_id: str, token_data: UserTokenData
    ) -> UserSessionResponse:
        data_dict = self._model_to_data_dict(token_data, user_id=user_id)
        async with self._session_scope() as session:
            await self._execute_statement(
                session,
                (
                    update(UserSession)
                    .where(UserSession.id == session_id)
                    .values(**data_dict)
                ),
            )
            result = await self._execute_statement(
                session, select(UserSession).where(UserSession.id == session_id)
            )
            user_session = result.scalar_one_or_none()
            if user_session is None:
                raise NotFoundError("User session not found after created")
            return self._user_session_to_response(user_session)

    async def delete_user_sessions(self, session_ids: list[str]):
        async with self._session_scope() as session:
            await self._execute_statement(
                session, delete(UserSession).where(UserSession.id.in_(session_ids))
            )

    def _user_session_to_response(
        self, user_session: UserSession
    ) -> UserSessionResponse:
        return UserSessionResponse(
            id=user_session.id,
            user_id=user_session.user_id,
            access_token=user_session.access_token,
            access_token_expired_at=user_session.access_token_expired_at,
            refresh_token=user_session.refresh_token,
            refresh_token_expired_at=user_session.refresh_token_expired_at,
            token_type="bearer",
        )
