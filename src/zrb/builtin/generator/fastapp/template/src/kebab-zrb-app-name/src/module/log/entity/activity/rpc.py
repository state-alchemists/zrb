from logging import Logger
from typing import Any, Mapping

from component.messagebus import Publisher
from component.repo import SearchFilter
from component.rpc import Caller, Server
from module.auth.schema.token import AccessTokenData
from module.log.integration.model.activity_model import activity_model
from module.log.schema.activity import ActivityData


def register_rpc(
    logger: Logger, rpc_server: Server, rpc_caller: Caller, publisher: Publisher
):
    logger.info('🥪 Register RPC handlers for "log.activity"')

    @rpc_server.register("log_get_activity")
    async def get(
        keyword: str,
        criterion: Mapping[str, Any],
        limit: int,
        offset: int,
        user_token_data: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        result = await activity_model.get(
            search_filter=SearchFilter(keyword=keyword, criterion=criterion),
            limit=limit,
            offset=offset,
        )
        return result.model_dump()

    @rpc_server.register("log_get_activity_by_id")
    async def get_by_id(
        id: str, user_token_data: Mapping[str, Any] = {}
    ) -> Mapping[str, Any]:
        row = await activity_model.get_by_id(id)
        return row.model_dump()

    @rpc_server.register("log_insert_activity")
    async def insert(
        data: Mapping[str, Any], user_token_data: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        user_token_data = AccessTokenData(**user_token_data)
        data["created_by"] = user_token_data.user_id
        data["updated_by"] = user_token_data.user_id
        row = await activity_model.insert(data=ActivityData(**data))
        return row.model_dump()

    @rpc_server.register("log_update_activity")
    async def update(
        id: str, data: Mapping[str, Any], user_token_data: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        user_token_data = AccessTokenData(**user_token_data)
        data["updated_by"] = user_token_data.user_id
        row = await activity_model.update(id=id, data=ActivityData(**data))
        return row.model_dump()

    @rpc_server.register("log_delete_activity")
    async def delete(id: str, user_token_data: Mapping[str, Any]) -> Mapping[str, Any]:
        user_token_data = AccessTokenData(**user_token_data)
        row = await activity_model.delete(id=id)
        return row.model_dump()
