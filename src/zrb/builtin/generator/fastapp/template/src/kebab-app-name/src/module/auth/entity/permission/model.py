from abc import ABC, abstractmethod
from core.model import Model, RepoModel
from module.auth.schema.permission import (
    Permission, PermissionData, PermissionResult
)
from module.auth.entity.permission.repo import PermissionRepo


class PermissionModel(
    Model[Permission, PermissionData, PermissionResult], ABC
):
    @abstractmethod
    async def ensure_permission(self, data: PermissionData):
        pass


class PermissionRepoModel(
    RepoModel[Permission, PermissionData, PermissionResult], PermissionModel
):
    schema_result_cls = PermissionResult

    def __init__(self, repo: PermissionRepo):
        self.repo = repo

    async def ensure_permission(self, data: PermissionData):
        try:
            await self.repo.get_by_name(data.name)
        except Exception as e:
            error_message = f'{e}'
            if error_message.lower().startswith('not found'):
                await self.repo.insert(data)
                return
            raise e
