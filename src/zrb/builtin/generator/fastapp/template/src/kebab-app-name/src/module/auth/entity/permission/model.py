from core.model import RepoModel
from module.auth.schema.permission import (
    Permission, PermissionData, PermissionResult
)
from module.auth.entity.permission.repo import PermissionRepo


class PermissionModel(
    RepoModel[Permission, PermissionData, PermissionResult]
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
