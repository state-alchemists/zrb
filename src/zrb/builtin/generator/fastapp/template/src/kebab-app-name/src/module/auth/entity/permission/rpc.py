from typing import Any, Mapping
from logging import Logger
from core.messagebus import Publisher
from core.rpc import Caller, Server
from core.repo import SearchFilter
from module.auth.component.model.permission_model import permission_model
from module.auth.schema.permission import PermissionData


def register_rpc(
    logger: Logger,
    rpc_server: Server,
    rpc_caller: Caller,
    publisher: Publisher
):
    logger.info('🥪 Register RPC handlers for "auth.permission"')

    @rpc_server.register('get_auth_permission')
    async def get(
        keyword: str, criterion: Mapping[str, Any],
        limit: int = 100, offset: int = 0
    ) -> Mapping[str, Any]:
        return permission_model.get(
            search_filter=SearchFilter(
                keyword=keyword, criterion=criterion
            ),
            limit=limit, offset=offset
        ).dict()

    @rpc_server.register('get_auth_permission_by_id')
    async def get_by_id(id: str) -> Mapping[str, Any]:
        return permission_model.get_by_id(id).dict()

    @rpc_server.register('insert_auth_permission')
    async def insert(data: Mapping[str, Any]) -> Mapping[str, Any]:
        return permission_model.insert(
            data=PermissionData(**data)
        ).dict()

    @rpc_server.register('update_auth_permission')
    async def update(id: str, data: Mapping[str, Any]) -> Mapping[str, Any]:
        return permission_model.update(
            id=id, data=PermissionData(**data)
        ).dict()

    @rpc_server.register('delete_auth_permission')
    async def delete(id: str) -> Mapping[str, Any]:
        return permission_model.delete(id=id).dict()
