from typing import Any, Mapping
from logging import Logger
from core.messagebus import Publisher
from core.rpc import Caller, Server
from core.repo import SearchFilter
from module.auth.component.model.user_model import user_model
from module.auth.schema.user import UserData, UserLogin
from module.auth.schema.token import TokenData


def register_rpc(
    logger: Logger,
    rpc_server: Server,
    rpc_caller: Caller,
    publisher: Publisher
):
    logger.info('🥪 Register RPC handlers for "auth.user"')

    @rpc_server.register('auth_user_is_admin')
    async def is_admin(id: str) -> bool:
        return await user_model.is_admin(id)

    @rpc_server.register('auth_user_is_guest')
    async def is_guest(id: str) -> bool:
        return await user_model.is_guest(id)

    @rpc_server.register('auth_user_is_having_permission')
    async def is_having_permission(id: str, permission_name: str) -> bool:
        return await user_model.is_having_permission(id, permission_name)

    @rpc_server.register('auth_login')
    async def login(login_data: Mapping[str, str]) -> str:
        return await user_model.login(UserLogin(**login_data))

    @rpc_server.register('auth_get_user')
    async def get(
        keyword: str,
        criterion: Mapping[str, Any],
        limit: int,
        offset: int,
        user_token_data: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        result = await user_model.get(
            search_filter=SearchFilter(
                keyword=keyword, criterion=criterion
            ),
            limit=limit,
            offset=offset
        )
        return result.dict()

    @rpc_server.register('auth_get_user_by_id')
    async def get_by_id(
        id: str,
        user_token_data: Mapping[str, Any] = {}
    ) -> Mapping[str, Any]:
        row = await user_model.get_by_id(id)
        return row.dict()

    @rpc_server.register('auth_insert_user')
    async def insert(
        data: Mapping[str, Any],
        user_token_data: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        user_token_data = TokenData(**user_token_data)
        data['created_by'] = user_token_data.user_id
        data['updated_by'] = user_token_data.user_id
        row = await user_model.insert(
            data=UserData(**data)
        )
        return row.dict()

    @rpc_server.register('auth_update_user')
    async def update(
        id: str,
        data: Mapping[str, Any],
        user_token_data: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        user_token_data = TokenData(**user_token_data)
        data['updated_by'] = user_token_data.user_id
        row = await user_model.update(
            id=id, data=UserData(**data)
        )
        return row.dict()

    @rpc_server.register('auth_delete_user')
    async def delete(
        id: str,
        user_token_data: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        user_token_data = TokenData(**user_token_data)
        row = await user_model.delete(id=id)
        return row.dict()
