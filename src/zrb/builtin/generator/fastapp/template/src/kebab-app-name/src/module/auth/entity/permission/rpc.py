from typing import Any, Mapping
from logging import Logger
from core.messagebus import Publisher
from core.rpc import Caller, Server
from core.repo import SearchFilter
from module.auth.component.model.permission_model import permission_model
from module.auth.schema.permission import PermissionData
from module.auth.schema.token import TokenData


def register_rpc(
    logger: Logger,
    rpc_server: Server,
    rpc_caller: Caller,
    publisher: Publisher
):
    logger.info('🥪 Register RPC handlers for "auth.permission"')

    @rpc_server.register('ensure_auth_permission')
    async def ensure(data: Mapping[str, Any]):
        await permission_model.ensure_permission(
            PermissionData(**data)
        )

    @rpc_server.register('get_auth_permission')
    async def get(
        keyword: str,
        criterion: Mapping[str, Any],
        limit: int,
        offset: int,
        user_token_data: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        result = await permission_model.get(
            search_filter=SearchFilter(
                keyword=keyword, criterion=criterion
            ),
            limit=limit,
            offset=offset
        )
        return result.dict()

    @rpc_server.register('get_auth_permission_by_id')
    async def get_by_id(
        id: str,
        user_token_data: Mapping[str, Any] = {}
    ) -> Mapping[str, Any]:
        row = await permission_model.get_by_id(id)
        return row.dict()

    @rpc_server.register('insert_auth_permission')
    async def insert(
        data: Mapping[str, Any],
        user_token_data: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        user_token_data = TokenData(**user_token_data)
        data['created_by'] = user_token_data.user_id
        data['updated_by'] = user_token_data.user_id
        row = await permission_model.insert(
            data=PermissionData(**data)
        )
        return row.dict()

    @rpc_server.register('update_auth_permission')
    async def update(
        id: str,
        data: Mapping[str, Any],
        user_token_data: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        user_token_data = TokenData(**user_token_data)
        data['updated_by'] = user_token_data.user_id
        row = await permission_model.update(
            id=id, data=PermissionData(**data)
        )
        return row.dict()

    @rpc_server.register('delete_auth_permission')
    async def delete(
        id: str,
        user_token_data: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        user_token_data = TokenData(**user_token_data)
        row = await permission_model.delete(id=id).dict()
        return row.dict()
