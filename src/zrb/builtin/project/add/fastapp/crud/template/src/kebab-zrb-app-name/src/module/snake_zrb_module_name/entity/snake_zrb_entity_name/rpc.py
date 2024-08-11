from logging import Logger
from typing import Any, Mapping

from component.messagebus import Publisher
from component.repo import SearchFilter
from component.rpc import Caller, Server
from module.auth.schema.token import AccessTokenData
from module.snake_zrb_module_name.integration.model.snake_zrb_entity_name_model import (
    snake_zrb_entity_name_model,
)
from module.snake_zrb_module_name.schema.snake_zrb_entity_name import (
    PascalZrbEntityNameData,
)


def register_rpc(
    logger: Logger, rpc_server: Server, rpc_caller: Caller, publisher: Publisher
):
    logger.info(
        '🥪 Register RPC handlers for "snake_zrb_module_name.snake_zrb_entity_name"'
    )

    @rpc_server.register("snake_zrb_module_name_get_snake_zrb_entity_name")
    async def get(
        keyword: str,
        criterion: Mapping[str, Any],
        limit: int,
        offset: int,
        user_token_data: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        result = await snake_zrb_entity_name_model.get(
            search_filter=SearchFilter(keyword=keyword, criterion=criterion),
            limit=limit,
            offset=offset,
        )
        return result.model_dump()

    @rpc_server.register("snake_zrb_module_name_get_snake_zrb_entity_name_by_id")
    async def get_by_id(
        id: str, user_token_data: Mapping[str, Any] = {}
    ) -> Mapping[str, Any]:
        row = await snake_zrb_entity_name_model.get_by_id(id)
        return row.model_dump()

    @rpc_server.register("snake_zrb_module_name_insert_snake_zrb_entity_name")
    async def insert(
        data: Mapping[str, Any], user_token_data: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        user_token_data = AccessTokenData(**user_token_data)
        data["created_by"] = user_token_data.user_id
        data["updated_by"] = user_token_data.user_id
        row = await snake_zrb_entity_name_model.insert(
            data=PascalZrbEntityNameData(**data)
        )
        return row.model_dump()

    @rpc_server.register("snake_zrb_module_name_update_snake_zrb_entity_name")
    async def update(
        id: str, data: Mapping[str, Any], user_token_data: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        user_token_data = AccessTokenData(**user_token_data)
        data["updated_by"] = user_token_data.user_id
        row = await snake_zrb_entity_name_model.update(
            id=id, data=PascalZrbEntityNameData(**data)
        )
        return row.model_dump()

    @rpc_server.register("snake_zrb_module_name_delete_snake_zrb_entity_name")
    async def delete(id: str, user_token_data: Mapping[str, Any]) -> Mapping[str, Any]:
        user_token_data = AccessTokenData(**user_token_data)
        row = await snake_zrb_entity_name_model.delete(id=id)
        return row.model_dump()
