import datetime
from typing import Any, Callable

import ulid
from my_app_name.common.base_db_repository import BaseDBRepository
from my_app_name.common.error import NotFoundError
from my_app_name.config import (
    APP_AUTH_GUEST_USER,
    APP_AUTH_GUEST_USER_PERMISSIONS,
    APP_AUTH_SUPER_USER,
    APP_AUTH_SUPER_USER_PASSWORD,
    APP_MAX_PARALLEL_SESSION,
    APP_SESSION_EXPIRE_MINUTES,
)
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
from sqlalchemy import and_
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql import ClauseElement, ColumnElement, Select
from sqlmodel import SQLModel, delete, insert, select, update

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

    def __init__(
        self,
        engine: Engine | AsyncEngine,
        super_user_username: str = APP_AUTH_SUPER_USER,
        super_user_password: str = APP_AUTH_SUPER_USER_PASSWORD,
        guest_user_username: str = APP_AUTH_GUEST_USER,
        guest_user_password: str = APP_AUTH_SUPER_USER_PASSWORD,
        guest_user_permission_names: list[str] = APP_AUTH_GUEST_USER_PERMISSIONS,
        max_parallel_session: int = APP_MAX_PARALLEL_SESSION,
        session_expire_minutes: int = APP_SESSION_EXPIRE_MINUTES,
        filter_param_parser: (
            Callable[[SQLModel, str], list[ClauseElement]] | None
        ) = None,
        sort_param_parser: Callable[[SQLModel, str], list[ColumnElement]] | None = None,
    ):
        super().__init__(
            engine=engine,
            filter_param_parser=filter_param_parser,
            sort_param_parser=sort_param_parser,
        )
        self._super_user_username = super_user_username
        self._super_user_passwored = super_user_password
        self._guest_user_username = guest_user_username
        self._guest_user_password = guest_user_password
        self._guest_user_permission_names = guest_user_permission_names
        self._max_parallel_session = max_parallel_session
        self._session_expire_minutes = session_expire_minutes
        self._super_user: User | None = None
        self._guest_user: User | None = None

    def _select(self) -> Select:
        now = datetime.datetime.now(datetime.timezone.utc)
        return (
            select(User, Role, Permission, UserSession)
            .join(UserRole, UserRole.user_id == User.id, isouter=True)
            .join(Role, Role.id == UserRole.role_id, isouter=True)
            .join(RolePermission, RolePermission.role_id == Role.id, isouter=True)
            .join(
                Permission, Permission.id == RolePermission.permission_id, isouter=True
            )
            .join(
                UserSession,
                and_(
                    UserSession.user_id == User.id,
                    UserSession.token_expired_at > now,
                ),
                isouter=True,
            )
        )

    def _rows_to_responses(self, rows: list[tuple[Any, ...]]) -> list[UserResponse]:
        user_map: dict[str, dict[str, Any]] = {}
        user_role_map: dict[str, list[str]] = {}
        user_permission_map: dict[str, list[str]] = {}
        for user, role, permission, _ in rows:
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
                permissions=list(data["permissions"]),
            )
            for data in user_map.values()
        ]

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
        async with self._session_scope() as session:
            await self._execute_statement(
                session, insert(UserRole).values(data_dict_list)
            )

    async def remove_all_roles(self, user_ids: list[str] = []):
        async with self._session_scope() as session:
            await self._execute_statement(
                session,
                delete(UserRole).where(UserRole.user_id._in(user_ids)),
            )

    async def get_by_credentials(self, username: str, password: str) -> UserResponse:
        rows = await self._select_to_response(
            lambda q: q.where(
                User.username == username,
                User.password == hash_password(password),
                User.active,
            )
        )
        return self._ensure_one(rows)

    async def get_by_token(self, token: str) -> UserResponse:
        rows = await self._select_to_response(
            lambda q: q.where(UserSession.token == token)
        )
        return self._ensure_one(rows)

    async def delete_expired_user_sessions(self, user_id: str):
        now = datetime.datetime.now(datetime.timezone.utc)
        async with self._session_scope() as session:
            await self._execute_statement(
                session,
                (
                    delete(UserSession).where(
                        UserSession.user_id == user_id,
                        UserSession.token_expired_at < now,
                        UserSession.refresh_token_expired_at < now,
                    )
                ),
            )

    async def get_user_sessions(self, user_id: str) -> list[UserSessionResponse]:
        now = datetime.datetime.now(datetime.timezone.utc)
        async with self._session_scope() as session:
            result = await self._execute_statement(
                session,
                (
                    select(UserSession).where(
                        UserSession.user_id == user_id,
                        UserSession.token_expired_at > now,
                    )
                ),
            )
            return [UserSessionResponse.model_validate(row[0] for row in result.all())]

    async def get_user_session_by_token(self, token: str) -> UserSessionResponse:
        now = datetime.datetime.now(datetime.timezone.utc)
        async with self._session_scope() as session:
            result = await self._execute_statement(
                session,
                (
                    select(UserSession).where(
                        UserSession.token == token, UserSession.token_expired_at > now
                    )
                ),
            )
            user_session = result.scalar_one_or_none()
            if user_session is None:
                raise NotFoundError("User session not found")
            return UserSession.model_validate(user_session)

    async def get_user_session_by_refresh_token(
        self, refresh_token: str
    ) -> UserSessionResponse:
        now = datetime.datetime.now(datetime.timezone.utc)
        async with self._session_scope() as session:
            result = await self._execute_statement(
                session,
                (
                    select(UserSession).where(
                        UserSession.refresh_token == refresh_token,
                        UserSession.refresh_token_expired_at > now,
                    )
                ),
            )
            user_session = result.scalar_one_or_none()
            if user_session is None:
                raise NotFoundError("User session not found")
            return UserSession.model_validate(user_session)

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

    async def delete_user_session(
        self, user_id: str, session_id: str
    ) -> UserSessionResponse:
        async with self._session_scope() as session:
            statement = select(UserSession).where(
                UserSession.id == session_id, UserSession.user_id == user_id
            )
            result = await self._execute_statement(session, statement)
            user_session = result.scalar_one_or_none()
            if not user_session:
                raise NotFoundError("User session not found")
            await self._execute_statement(
                session, delete(UserSession).where(UserSession.id == user_session.id)
            )
            return self.db_model(**user_session.model_dump())
