from component.messagebus.messagebus import Publisher
from module.auth.entity.permission.repo import PermissionRepo
from module.auth.schema.permission import Permission, PermissionData, PermissionResult
from module.log.component.historical_repo_model import HistoricalRepoModel


class PermissionModel(
    HistoricalRepoModel[Permission, PermissionData, PermissionResult]
):
    schema_result_cls = PermissionResult
    log_entity_name = "permission"

    def __init__(self, repo: PermissionRepo, publisher: Publisher):
        super().__init__(repo, publisher)

    async def ensure_permission(self, data: PermissionData):
        try:
            await self.repo.get_by_name(data.name)
        except Exception as e:
            error_message = f"{e}"
            if error_message.lower().startswith("not found"):
                await self.repo.insert(data)
                return
            raise e
