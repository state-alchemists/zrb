from abc import ABC
from core.model import Model, RepoModel
from module.auth.schema.permission import (
    Permission, PermissionData, PermissionResult
)


class PermissionModel(
    Model[Permission, PermissionData, PermissionResult], ABC
):
    pass


class PermissionRepoModel(
    RepoModel[Permission, PermissionData, PermissionResult], PermissionModel
):
    schema_result_cls = PermissionResult
