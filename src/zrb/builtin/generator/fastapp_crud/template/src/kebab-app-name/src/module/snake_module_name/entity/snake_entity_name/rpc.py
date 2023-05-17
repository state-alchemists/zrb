from typing import Any, Mapping
from logging import Logger
from core.messagebus import Publisher
from core.rpc import Caller, Server
from core.repo import SearchFilter
from module.snake_module_name.component.model.snake_entity_name_model import (
    snake_entity_name_model
)
from module.snake_module_name.schema.snake_entity_name import PascalEntityNameData
from module.auth.schema.token import AccessTokenData


def register_rpc(
    logger: Logger,
    rpc_server: Server,
    rpc_caller: Caller,
    publisher: Publisher
):
    logger.info('🥪 Register RPC handlers for "snake_module_name.snake_entity_name"')

    @rpc_server.register('snake_module_name_get_snake_entity_name')
    async def get(
        keyword: str,
        criterion: Mapping[str, Any],
        limit: int,
        offset: int,
        user_token_data: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        result = await snake_entity_name_model.get(
            search_filter=SearchFilter(
                keyword=keyword, criterion=criterion
            ),
            limit=limit,
            offset=offset
        )
        return result.dict()

    @rpc_server.register('snake_module_name_get_snake_entity_name_by_id')
    async def get_by_id(
        id: str,
        user_token_data: Mapping[str, Any] = {}
    ) -> Mapping[str, Any]:
        row = await snake_entity_name_model.get_by_id(id)
        return row.dict()

    @rpc_server.register('snake_module_name_insert_snake_entity_name')
    async def insert(
        data: Mapping[str, Any],
        user_token_data: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        user_token_data = AccessTokenData(**user_token_data)
        data['created_by'] = user_token_data.user_id
        data['updated_by'] = user_token_data.user_id
        row = await snake_entity_name_model.insert(
            data=PascalEntityNameData(**data)
        )
        return row.dict()

    @rpc_server.register('snake_module_name_update_snake_entity_name')
    async def update(
        id: str,
        data: Mapping[str, Any],
        user_token_data: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        user_token_data = AccessTokenData(**user_token_data)
        data['updated_by'] = user_token_data.user_id
        row = await snake_entity_name_model.update(
            id=id, data=PascalEntityNameData(**data)
        )
        return row.dict()

    @rpc_server.register('snake_module_name_delete_snake_entity_name')
    async def delete(
        id: str,
        user_token_data: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        user_token_data = AccessTokenData(**user_token_data)
        row = await snake_entity_name_model.delete(id=id)
        return row.dict()
