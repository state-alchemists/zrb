from typing import List, Mapping, Optional

from component.messagebus.messagebus import Publisher
from module.auth.component import AccessTokenUtil, RefreshTokenUtil
from module.auth.entity.permission.model import PermissionModel
from module.auth.entity.user.repo import UserRepo
from module.auth.schema.token import AccessTokenData, RefreshTokenData, TokenResponse
from module.auth.schema.user import User, UserData, UserLogin, UserResult
from module.log.component.historical_repo_model import HistoricalRepoModel


class UserModel(HistoricalRepoModel[User, UserData, UserResult]):
    schema_result_cls = UserResult
    log_entity_name = "user"

    def __init__(
        self,
        repo: UserRepo,
        publisher: Publisher,
        permission_model: PermissionModel,
        access_token_util: AccessTokenUtil,
        access_token_expire_seconds: int | float,
        refresh_token_util: RefreshTokenUtil,
        refresh_token_expire_seconds: int | float,
        guest_user: User,
        admin_user: Optional[User] = None,
        admin_user_password: str = "",
    ):
        super().__init__(repo, publisher)
        self.permission_model = permission_model
        self.access_token_util = access_token_util
        self.access_token_expire_seconds = access_token_expire_seconds
        self.refresh_token_util = refresh_token_util
        self.refresh_token_expire_seconds = refresh_token_expire_seconds
        self.guest_user = guest_user
        self.admin_user = admin_user
        self.admin_user_pasword = admin_user_password

    async def insert(self, data: UserData) -> User:
        if self.admin_user is not None and data.username == self.admin_user.username:
            raise ValueError(f"Invalid username: {data.username} is used by admin")
        if data.username == self.guest_user.username:
            raise ValueError(f"Invalid username: {data.username} is used by guest")
        return await super().insert(data)

    async def update(self, id: str, data: UserData) -> User:
        if self.admin_user is not None:
            if self.is_admin(id):
                raise ValueError("Forbidden: editting admin user is not permitted")
            if data.username == self.admin_user.username:
                raise ValueError(f"Invalid username: {data.username} is used by admin")
        if self.is_guest(id):
            raise ValueError("Forbidden: editting guest user is not permitted")
        if data.username == self.guest_user.username:
            raise ValueError(f"Invalid username: {data.username} is used by guest")
        return await super().update(id, data)

    async def delete(self, id: str) -> User:
        if self.admin_user is not None and self.is_admin(id):
            raise ValueError("Forbidden: deleting admin user is not permitted")
        if self.is_guest(id):
            raise ValueError("Forbidden: deleting guest user is not permitted")
        return await super().delete(id)

    async def get_by_id(self, id: str) -> User:
        if self.admin_user is not None and self.is_admin(id):
            return self.admin_user
        if id == self.guest_user.id:
            return self.guest_user
        return await super().get_by_id(id)

    async def is_authorized(
        self, id: str, *permission_names: str
    ) -> Mapping[str, bool]:
        user = await self.get_by_id(id)
        if self.is_admin(user.id):
            return {permission_name: True for permission_name in permission_names}
        user_permission_names = self._get_permission_names(user)
        return {
            permission_name: permission_name in user_permission_names
            for permission_name in permission_names
        }

    def _get_permission_names(self, user: User) -> List[str]:
        permission_names = [permission.name for permission in user.permissions]
        for group in user.groups:
            additional_permission_names = [
                permission.name
                for permission in group.permissions
                if permission.name not in permission_names
            ]
            permission_names += additional_permission_names
        return permission_names

    def is_guest(self, id: str) -> bool:
        return id == self.guest_user.id

    def is_admin(self, id: str) -> bool:
        if self.admin_user is None:
            return False
        return id == self.admin_user.id

    async def create_auth_token(self, user_login: UserLogin) -> TokenResponse:
        user = await self._get_user_by_user_login(user_login)
        return TokenResponse(
            access_token=self._get_access_token(user),
            refresh_token=self._get_refresh_token(user),
            token_type="bearer",
        )

    async def refresh_auth_token(
        self, refresh_token: str, access_token: str
    ) -> TokenResponse:
        access_token_data = self.access_token_util.decode(
            access_token, parse_expired_token=True
        )
        refresh_token_data = self.refresh_token_util.decode(refresh_token)
        if access_token_data.user_id != refresh_token_data.user_id:
            raise ValueError("Unmatch refresh and access token")
        user = await self.get_by_id(refresh_token_data.user_id)
        return TokenResponse(
            access_token=self._get_access_token(user),
            refresh_token=self._get_refresh_token(user),
            token_type="bearer",
        )

    def _get_access_token(self, user: User) -> str:
        access_token_data = AccessTokenData(
            user_id=user.id,
            username=user.username,
            expire_seconds=self.access_token_expire_seconds,
        )
        return self.access_token_util.encode(access_token_data)

    def _get_refresh_token(self, user: User) -> str:
        refresh_token_data = RefreshTokenData(
            user_id=user.id, expire_seconds=self.refresh_token_expire_seconds
        )
        return self.refresh_token_util.encode(refresh_token_data)

    async def _get_user_by_user_login(self, user_login: UserLogin) -> User:
        if user_login.identity == "":
            raise ValueError("Invalid identity: Identity is empty")
        if (
            self.admin_user is not None
            and user_login.password == self.admin_user_pasword
            and (
                user_login.identity == self.admin_user.username
                or user_login.identity == self.admin_user.email
                or user_login.identity == self.admin_user.phone
            )
        ):
            return self.admin_user
        return await self.repo.get_by_user_login(user_login)
