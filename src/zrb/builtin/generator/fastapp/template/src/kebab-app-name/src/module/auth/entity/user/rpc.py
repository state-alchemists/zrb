from typing import Any, Mapping
from logging import Logger
from core.messagebus import Publisher
from core.rpc import Caller, Server
from core.repo import SearchFilter
from module.auth.component.model import user_model
from module.auth.schema.user import UserData, UserLogin


def register_rpc(
    logger: Logger,
    rpc_server: Server,
    rpc_caller: Caller,
    publisher: Publisher
):
    logger.info('🥪 Register RPC handlers for "auth.user"')

    @rpc_server.register('auth_login')
    async def login(login_data: Mapping[str, str]) -> str:
        return user_model.login(UserLogin(**login_data))

    @rpc_server.register('get_auth_user')
    async def get(
        keyword: str, criterion: Mapping[str, Any],
        limit: int = 100, offset: int = 0
    ) -> Mapping[str, Any]:
        return user_model.get(
            search_filter=SearchFilter(
                keyword=keyword, criterion=criterion
            ),
            limit=limit, offset=offset
        ).dict()

    @rpc_server.register('get_auth_user_by_id')
    async def get_by_id(id: str) -> Mapping[str, Any]:
        return user_model.get_by_id(id).dict()

    @rpc_server.register('insert_auth_user')
    async def insert(data: Mapping[str, Any]) -> Mapping[str, Any]:
        return user_model.insert(
            data=UserData(**data)
        ).dict()

    @rpc_server.register('update_auth_user')
    async def update(id: str, data: Mapping[str, Any]) -> Mapping[str, Any]:
        return user_model.update(
            id=id, data=UserData(**data)
        ).dict()

    @rpc_server.register('delete_auth_user')
    async def delete(id: str) -> Mapping[str, Any]:
        return user_model.delete(id=id).dict()
