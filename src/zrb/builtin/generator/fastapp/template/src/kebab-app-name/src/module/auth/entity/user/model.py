from abc import ABC
from core.model import Model, RepoModel
from module.auth.schema.user import (
    User, UserData, UserResult
)


class UserModel(
    Model[User, UserData, UserResult], ABC
):
    pass


class UserRepoModel(
    RepoModel[User, UserData, UserResult], UserModel
):
    schema_result_cls = UserResult
