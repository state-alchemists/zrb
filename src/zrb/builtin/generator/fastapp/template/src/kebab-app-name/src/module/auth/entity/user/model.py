from typing import List
from abc import ABC, abstractmethod
from core.model import Model, RepoModel
from module.auth.schema.user import (
    User, UserData, UserResult, UserLogin
)
from module.auth.schema.permission import Permission
from module.auth.entity.user.repo import UserRepo
from module.auth.schema.token import TokenData
from module.auth.core.token_util.token_util import TokenUtil


class UserModel(
    Model[User, UserData, UserResult], ABC
):
    @abstractmethod
    def login(self, user_login: UserLogin) -> str:
        pass


class UserRepoModel(
    RepoModel[User, UserData, UserResult], UserModel
):
    schema_result_cls = UserResult

    def __init__(
        self, repo: UserRepo, token_util: TokenUtil, expire_seconds: int = 300
    ):
        self.repo = repo
        self.token_util = token_util
        self.expire_seconds = expire_seconds

    def login(self, user_login: UserLogin) -> str:
        user = self._get_by_user_login(user_login)
        return self._get_token(user)

    def _get_token(self, user: User) -> str:
        token_data = TokenData(
            user_id=user.id,
            username=user.username,
            permissions=[
                permission.id for permission in self._get_permissions(user)
            ],
            expire_seconds=self.expire_seconds
        )
        return self.token_util.encode(token_data)

    def _get_permissions(self, user: User) -> List[Permission]:
        permissions: List[Permission] = list(user.permissions)
        for group in user.groups:
            group_permissions = group.permissions
            for group_permission in group_permissions:
                if group_permission in permissions:
                    continue
                permissions.append(group_permission)
        return permissions

    def _get_by_user_login(self, user_login: UserLogin) -> User:
        return self.repo.get_by_user_login(user_login)
