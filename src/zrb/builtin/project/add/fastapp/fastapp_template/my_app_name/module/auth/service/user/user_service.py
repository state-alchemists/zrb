import datetime
from logging import Logger

from jose import jwt
from my_app_name.common.base_service import BaseService
from my_app_name.common.error import ForbiddenError, NotFoundError
from my_app_name.module.auth.service.user.repository.user_repository import (
    UserRepository,
)
from my_app_name.schema.user import (
    AuthUserResponse,
    MultipleUserResponse,
    UserCreateWithRolesAndAudit,
    UserCredentials,
    UserResponse,
    UserSessionResponse,
    UserTokenData,
    UserUpdateWithRolesAndAudit,
)
from pydantic import BaseModel


class UserServiceConfig(BaseModel):
    super_user: str
    super_user_password: str
    guest_user: str = "guest"
    guest_user_permissions: list[str] = []
    max_parallel_session: int = 1
    access_token_expire_minutes: int = 30
    refresh_token_expire_minutes: int = 1440
    secret_key: str = "my-secret-key"
    prioritize_new_session: bool = True


class UserService(BaseService):

    def __init__(
        self, logger: Logger, user_repository: UserRepository, config: UserServiceConfig
    ):
        super().__init__(logger)
        self.user_repository = user_repository
        self.config = config

    @BaseService.route(
        "/api/v1/current-user",
        methods=["get"],
        response_model=AuthUserResponse,
    )
    async def get_current_user(self, access_token: str | None) -> AuthUserResponse:
        if access_token is None or access_token == "":
            return self._get_guest_user()
        try:
            user_session = await self.user_repository.get_user_session_by_access_token(
                access_token
            )
            user_id = user_session.user_id
            if user_id == self.config.super_user:
                return self._get_super_user()
            user = await self.user_repository.get_by_id(user_id)
            return self._to_auth_user_response(user)
        except NotFoundError:
            return self._get_guest_user()

    @BaseService.route(
        "/api/v1/user-sessions",
        methods=["post"],
        response_model=UserSessionResponse,
    )
    async def create_user_session(
        self, credentials: UserCredentials
    ) -> UserSessionResponse:
        current_user = await self._get_user_by_credentials(credentials)
        await self.user_repository.delete_expired_user_sessions(current_user.id)
        user_sessions = await self.user_repository.get_active_user_sessions(
            current_user.id
        )
        user_session_count = len(user_sessions)
        if user_session_count >= self.config.max_parallel_session:
            await self._handle_excess_sessions(user_sessions)
        token_data = self._create_user_token_data(current_user.username)
        return await self.user_repository.create_user_session(
            user_id=current_user.id, token_data=token_data
        )

    @BaseService.route(
        "/api/v1/user-sessions",
        methods=["put"],
        response_model=UserSessionResponse,
    )
    async def update_user_session(self, refresh_token: str) -> UserSessionResponse:
        current_user = await self._get_auth_user_by_refresh_token(refresh_token)
        current_user_session = (
            await self.user_repository.get_user_session_by_refresh_token(refresh_token)
        )
        token_data = self._create_user_token_data(current_user.username)
        return await self.user_repository.update_user_session(
            user_id=current_user.id,
            session_id=current_user_session.id,
            token_data=token_data,
        )

    @BaseService.route(
        "/api/v1/user-sessions",
        methods=["delete"],
        response_model=UserSessionResponse,
    )
    async def delete_user_session(self, refresh_token: str) -> UserSessionResponse:
        current_user_session = (
            await self.user_repository.get_user_session_by_refresh_token(refresh_token)
        )
        await self.user_repository.delete_user_sessions([current_user_session.id])
        return current_user_session

    @BaseService.route(
        "/api/v1/users/{user_id}",
        methods=["get"],
        response_model=UserResponse,
    )
    async def get_user_by_id(self, user_id: str) -> UserResponse:
        return await self.user_repository.get_by_id(user_id)

    @BaseService.route(
        "/api/v1/users",
        methods=["get"],
        response_model=MultipleUserResponse,
    )
    async def get_users(
        self,
        page: int = 1,
        page_size: int = 10,
        sort: str | None = None,
        filter: str | None = None,
    ) -> MultipleUserResponse:
        users = await self.user_repository.get(page, page_size, filter, sort)
        count = await self.user_repository.count(filter)
        return MultipleUserResponse(data=users, count=count)

    @BaseService.route(
        "/api/v1/users/bulk",
        methods=["post"],
        response_model=list[UserResponse],
    )
    async def create_user_bulk(
        self, data: list[UserCreateWithRolesAndAudit]
    ) -> list[UserResponse]:
        bulk_role_names = [row.get_role_names() for row in data]
        for role_names in bulk_role_names:
            await self.user_repository.validate_role_names(role_names)
        bulk_user_data = [row.get_user_create_with_audit() for row in data]
        users = await self.user_repository.create_bulk(bulk_user_data)
        if len(users) > 0:
            created_by = users[0].created_by
            await self.user_repository.add_roles(
                data={user.id: bulk_role_names[i] for i, user in enumerate(users)},
                created_by=created_by,
            )
        return await self.user_repository.get_by_ids([user.id for user in users])

    @BaseService.route(
        "/api/v1/users",
        methods=["post"],
        response_model=UserResponse,
    )
    async def create_user(self, data: UserCreateWithRolesAndAudit) -> UserResponse:
        role_names = data.get_role_names()
        await self.user_repository.validate_role_names(role_names)
        user_data = data.get_user_create_with_audit()
        user = await self.user_repository.create(user_data)
        await self.user_repository.add_roles(
            data={user.id: role_names}, created_by=user.created_by
        )
        return await self.user_repository.get_by_id(user.id)

    @BaseService.route(
        "/api/v1/users/bulk",
        methods=["put"],
        response_model=list[UserResponse],
    )
    async def update_user_bulk(
        self, user_ids: list[str], data: UserUpdateWithRolesAndAudit
    ) -> list[UserResponse]:
        bulk_role_names = [row.get_role_names() for row in data]
        for role_names in bulk_role_names:
            await self.user_repository.validate_role_names(role_names)
        bulk_user_data = [row.get_user_update_with_audit() for row in data]
        await self.user_repository.update_bulk(user_ids, bulk_user_data)
        if len(user_ids) > 0:
            updated_by = bulk_user_data[0].updated_by
            await self.user_repository.remove_all_roles(user_ids)
            await self.user_repository.add_roles(
                data={
                    user_id: bulk_role_names[i] for i, user_id in enumerate(user_ids)
                },
                updated_by=updated_by,
            )
        return await self.user_repository.get_by_ids(user_ids)

    @BaseService.route(
        "/api/v1/users/{user_id}",
        methods=["put"],
        response_model=UserResponse,
    )
    async def update_user(
        self, user_id: str, data: UserUpdateWithRolesAndAudit
    ) -> UserResponse:
        role_names = data.get_role_names()
        await self.user_repository.validate_role_names(role_names)
        user_data = data.get_user_update_with_audit()
        await self.user_repository.update(user_id, user_data)
        await self.user_repository.remove_all_roles([user_id])
        await self.user_repository.add_roles(
            data={user_id: role_names}, created_by=user_data.updated_by
        )
        return await self.user_repository.get_by_id(user_id)

    @BaseService.route(
        "/api/v1/users/bulk",
        methods=["delete"],
        response_model=list[UserResponse],
    )
    async def delete_user_bulk(
        self, user_ids: list[str], deleted_by: str
    ) -> list[UserResponse]:
        roles = await self.user_repository.get_by_ids(user_ids)
        await self.user_repository.delete_bulk(user_ids)
        await self.user_repository.remove_all_roles(user_ids)
        return roles

    @BaseService.route(
        "/api/v1/users/{user_id}",
        methods=["delete"],
        response_model=UserResponse,
    )
    async def delete_user(self, user_id: str, deleted_by: str) -> UserResponse:
        user = await self.user_repository.get_by_id(user_id)
        await self.user_repository.delete(user_id)
        await self.user_repository.remove_all_roles([user_id])
        return user

    async def _get_auth_user_by_refresh_token(
        self, refresh_token: str
    ) -> AuthUserResponse:
        if refresh_token is None or refresh_token == "":
            raise NotFoundError("User not found")
        user_session = await self.user_repository.get_user_session_by_refresh_token(
            refresh_token
        )
        user_id = user_session.user_id
        if user_id == self.config.super_user:
            return self._get_super_user()
        user = await self.user_repository.get_by_id(user_id)
        return self._to_auth_user_response(user)

    async def _get_user_by_credentials(
        self, credentials: UserCredentials
    ) -> AuthUserResponse:
        if (
            credentials.username == self.config.super_user
            and credentials.password == self.config.super_user_password
        ):
            return self._get_super_user()
        user = await self.user_repository.get_by_credentials(
            username=credentials.username,
            password=credentials.password,
        )
        return self._to_auth_user_response(user)

    def _to_auth_user_response(self, user_response: UserResponse) -> AuthUserResponse:
        return AuthUserResponse(
            **user_response.model_dump(), is_guest=False, is_super_user=False
        )

    def _get_guest_user(self):
        return AuthUserResponse(
            id=self.config.guest_user,
            username=self.config.guest_user,
            active=True,
            role_names=[],
            permission_names=self.config.guest_user_permissions,
            is_guest=True,
            is_super_user=False,
        )

    def _get_super_user(self):
        return AuthUserResponse(
            id=self.config.super_user,
            username=self.config.super_user,
            active=True,
            role_names=[],
            permission_names=[],
            is_guest=False,
            is_super_user=True,
        )

    async def _handle_excess_sessions(self, active_sessions: list[UserSessionResponse]):
        """Handles excess user sessions by deleting the oldest if necessary."""
        if not self.config.prioritize_new_session:
            raise ForbiddenError("No additional session allowed")
        # Sort sessions by expiration and remove the oldest ones
        sessions_to_delete = sorted(
            active_sessions, key=lambda s: s.refresh_token_expired_at
        )
        excess_count = len(active_sessions) + 1 - self.config.max_parallel_session
        await self.user_repository.delete_user_sessions(
            [session.id for session in sessions_to_delete[:excess_count]]
        )

    def _create_user_token_data(self, username: str) -> UserTokenData:
        now = datetime.datetime.now(datetime.timezone.utc)
        access_token_expire_at = now + datetime.timedelta(
            minutes=self.config.access_token_expire_minutes
        )
        refresh_token_expire_at = now + datetime.timedelta(
            minutes=self.config.refresh_token_expire_minutes
        )
        return UserTokenData(
            access_token=self._generate_access_token(
                username=username,
                expire_at=access_token_expire_at,
            ),
            refresh_token=self._generate_refresh_token(
                username=username,
                expire_at=refresh_token_expire_at,
            ),
            access_token_expired_at=access_token_expire_at,
            refresh_token_expired_at=refresh_token_expire_at,
        )

    def _generate_access_token(
        self, username: str, expire_at: datetime.datetime
    ) -> str:
        return self._generate_user_token(
            username=username, expire_at=expire_at, token_type="access"
        )

    def _generate_refresh_token(
        self, username: str, expire_at: datetime.datetime
    ) -> str:
        return self._generate_user_token(
            username=username, expire_at=expire_at, token_type="refresh"
        )

    def _generate_user_token(
        self, username: str, expire_at: datetime.datetime, token_type: str
    ) -> str:
        to_encode = {"sub": username, "exp": expire_at, "type": token_type}
        return jwt.encode(to_encode, self.config.secret_key)
