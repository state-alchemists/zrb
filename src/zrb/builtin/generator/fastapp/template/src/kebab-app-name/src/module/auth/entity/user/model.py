from typing import Optional
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
        if (
            self.admin_user is not None and
            data.username == self.admin_user.username
        ):
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
            if id == self.admin_user.id:
                raise ValueError(
                    'Forbidden: editting admin user is not permitted'
                )
            if data.username == self.admin_user.username:
                raise ValueError(
                    'Invalid username: {data.username} is used by admin'
                )
        if id == self.guest_user.id:
            raise ValueError(
                'Forbidden: editting guest user is not permitted'
            )
        if data.username == self.guest_user.username:
            raise ValueError(
                'Invalid username: {data.username} is used by guest'
            )
        return await super().update(id, data)

    async def delete(self, id: str) -> User:
        if (
            self.admin_user is not None and
            id == self.admin_user.id
        ):
            raise ValueError(
                'Forbidden: deleting admin user is not permitted'
            )
        if id == self.guest_user.id:
            raise ValueError(
                'Forbidden: deleting guest user is not permitted'
            )
        return await super().delete(id)

    async def is_having_permission(
        self, id: str, permission_name: str
    ) -> bool:
        if await self.is_admin(id):
            return True
        if self.is_guest(id):
            return self._is_user_having_permission(
                self.guest_user, permission_name
            )
        user = await self.get_by_id(id)
        return self._is_user_having_permission(user, permission_name)

    async def is_guest(self, id: str) -> bool:
        return id == self.guest_user.id

    async def is_admin(self, id: str) -> bool:
        if self.admin_user is None:
            return False
        return id == self.admin_user.id

    async def login(self, user_login: UserLogin) -> str:
        if user_login.identity == '':
            raise ValueError('Invalid identity: Identity is not provided')
        if (
            self.admin_user is not None
            and user_login.password == self.admin_user_pasword
            and (
                user_login.identity == self.admin_user.username or
                user_login.identity == self.admin_user.email or
                user_login.identity == self.admin_user.phone
            )
        ):
            return self._get_token(self.admin_user)
        user = await self._get_user_by_user_login(user_login)
        return self._get_token(user)

    def _is_user_having_permission(
        self, user: User, permission_name: str
    ) -> bool:
        user_permission_names = [
            permission.name for permission in user.permissions
        ]
        if permission_name in user_permission_names:
            return True
        for group in user.groups:
            group_permission_names = [
                permission.name for permission in group.permissions
            ]
            if permission_name in group_permission_names:
                return True
        return False

    def _get_token(self, user: User) -> str:
        token_data = TokenData(
            user_id=user.id,
            username=user.username,
            expire_seconds=self.expire_seconds
        )
        return self.token_util.encode(token_data)

    async def _get_user_by_user_login(self, user_login: UserLogin) -> User:
        return await self.repo.get_by_user_login(user_login)
