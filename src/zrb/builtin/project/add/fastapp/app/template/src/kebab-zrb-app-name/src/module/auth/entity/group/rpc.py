from logging import Logger
from typing import Any, Mapping

from component.messagebus import Publisher
from component.repo import SearchFilter
from component.rpc import Caller, Server
from module.auth.integration.model.group_model import group_model
from module.auth.schema.group import GroupData
from module.auth.schema.token import AccessTokenData


def register_rpc(
    logger: Logger, rpc_server: Server, rpc_caller: Caller, publisher: Publisher
):
    logger.info('🥪 Register RPC handlers for "auth.group"')

    @rpc_server.register("auth_get_group")
    async def get(
        keyword: str,
        criterion: Mapping[str, Any],
        limit: int,
        offset: int,
        user_token_data: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        result = await group_model.get(
            search_filter=SearchFilter(keyword=keyword, criterion=criterion),
            limit=limit,
            offset=offset,
        )
        return result.model_dump()

    @rpc_server.register("auth_get_group_by_id")
    async def get_by_id(
        id: str, user_token_data: Mapping[str, Any] = {}
    ) -> Mapping[str, Any]:
        row = await group_model.get_by_id(id)
        return row.model_dump()

    @rpc_server.register("auth_insert_group")
    async def insert(
        data: Mapping[str, Any], user_token_data: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        user_token_data: AccessTokenData = AccessTokenData(**user_token_data)
        data["created_by"] = user_token_data.user_id
        data["updated_by"] = user_token_data.user_id
        row = await group_model.insert(data=GroupData(**data))
        return row.model_dump()

    @rpc_server.register("auth_update_group")
    async def update(
        id: str, data: Mapping[str, Any], user_token_data: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        user_token_data: AccessTokenData = AccessTokenData(**user_token_data)
        data["updated_by"] = user_token_data.user_id
        row = await group_model.update(id=id, data=GroupData(**data))
        return row.model_dump()

    @rpc_server.register("auth_delete_group")
    async def delete(id: str, user_token_data: Mapping[str, Any]) -> Mapping[str, Any]:
        user_token_data = AccessTokenData(**user_token_data)
        row = await group_model.delete(id=id)
        return row.model_dump()
