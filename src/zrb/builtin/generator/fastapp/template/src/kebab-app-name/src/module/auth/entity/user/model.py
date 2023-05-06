from typing import Optional, List, Mapping
from core.model import RepoModel
from module.auth.schema.user import (
    User, UserData, UserResult, UserLogin
)
from module.auth.entity.user.repo import UserRepo
from module.auth.schema.token import TokenData
from module.auth.core import TokenUtil
from module.auth.entity.permission.model import PermissionModel


class UserModel(
    RepoModel[User, UserData, UserResult]
):
    schema_result_cls = UserResult

    def __init__(
        self,
        repo: UserRepo,
        permission_model: PermissionModel,
        token_util: TokenUtil,
        expire_seconds: int,
        guest_user: User,
        admin_user: Optional[User] = None,
        admin_user_password: str = ''
    ):
        self.repo = repo
        self.permission_model = permission_model
        self.token_util = token_util
        self.expire_seconds = expire_seconds
        self.guest_user = guest_user
        self.admin_user = admin_user
        self.admin_user_pasword = admin_user_password

    async def insert(self, data: UserData) -> User:
        if self.admin_user is not None and self.is_admin(id):
            raise ValueError(
                'Invalid username: {data.username} is used by admin'
            )
        if data.username == self.guest_user.username:
            raise ValueError(
                'Invalid username: {data.username} is used by guest'
            )
        return await super().insert(data)

    async def update(self, id: str, data: UserData) -> User:
        if self.admin_user is not None:
            if self.is_admin(id):
                raise ValueError(
                    'Forbidden: editting admin user is not permitted'
                )
            if data.username == self.admin_user.username:
                raise ValueError(
                    'Invalid username: {data.username} is used by admin'
                )
        if self.is_guest(id):
            raise ValueError(
                'Forbidden: editting guest user is not permitted'
            )
        if data.username == self.guest_user.username:
            raise ValueError(
                'Invalid username: {data.username} is used by guest'
            )
        return await super().update(id, data)

    async def delete(self, id: str) -> User:
        if self.admin_user is not None and self.is_admin(id):
            raise ValueError(
                'Forbidden: deleting admin user is not permitted'
            )
        if self.is_guest(id):
            raise ValueError(
                'Forbidden: deleting guest user is not permitted'
            )
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
            return {
                permission_name: True for permission_name in permission_names
            }
        user_permission_names = self._get_permission_names(user)
        return {
            permission_name: permission_name in user_permission_names
            for permission_name in permission_names
        }

    def _get_permission_names(self, user: User) -> List[str]:
        permission_names = [
            permission.name for permission in user.permissions
        ]
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

    async def create_token(self, user_login: UserLogin) -> str:
        user = await self._get_user_by_user_login(user_login)
        return self._get_token(user)

    async def refresh_token(self, auth_token_str: str) -> str:
        user = await self._get_user_by_token(auth_token_str)
        return self._get_token(user)

    def _get_token(self, user: User) -> str:
        token_data = TokenData(
            user_id=user.id,
            username=user.username,
            expire_seconds=self.expire_seconds
        )
        return self.token_util.encode(token_data)

    async def _get_user_by_user_login(self, user_login: UserLogin) -> User:
        if user_login.identity == '':
            raise ValueError('Invalid identity: Identity is empty')
        if (
            self.admin_user is not None
            and user_login.password == self.admin_user_pasword
            and (
                user_login.identity == self.admin_user.username or
                user_login.identity == self.admin_user.email or
                user_login.identity == self.admin_user.phone
            )
        ):
            return self.admin_user
        return await self.repo.get_by_user_login(user_login)

    async def _get_user_by_token(self, token: str) -> User:
        token_data = self.token_util.decode(token)
        return await self.get_by_id(token_data.user_id)
