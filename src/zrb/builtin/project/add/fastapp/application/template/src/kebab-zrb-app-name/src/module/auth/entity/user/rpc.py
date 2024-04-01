from logging import Logger
from typing import Any, List, Mapping, Union

from component.messagebus import Publisher
from component.repo import SearchFilter
from component.rpc import Caller, Server
from module.auth.integration.model.user_model import user_model
from module.auth.schema.token import AccessTokenData
from module.auth.schema.user import UserData, UserLogin


def register_rpc(
    logger: Logger, rpc_server: Server, rpc_caller: Caller, publisher: Publisher
):
    logger.info('🥪 Register RPC handlers for "auth.user"')

    @rpc_server.register("auth_user_is_admin")
    async def user_is_admin(id: str) -> bool:
        """
        Used by RPC Authenticator
        """
        return await user_model.is_admin(id)

    @rpc_server.register("auth_user_is_guest")
    async def user_is_guest(id: str) -> bool:
        """
        Used by RPC Authenticator
        """
        return await user_model.is_guest(id)

    @rpc_server.register("auth_is_user_authorized")
    async def is_user_having_permission(
        id: str, permission_name: Union[str, List[str]]
    ) -> Mapping[str, bool]:
        """
        Used by RPC Authenticator
        """
        if isinstance(permission_name, str):
            return await user_model.is_authorized(id, permission_name)
        return await user_model.is_authorized(id, *permission_name)

    @rpc_server.register("auth_create_token")
    async def create_token(login_data: Mapping[str, str]) -> Mapping[str, str]:
        result = await user_model.create_auth_token(UserLogin(**login_data))
        return result.model_dump()

    @rpc_server.register("auth_refresh_token")
    async def refresh_token(refresh_token: str, access_token: str) -> Mapping[str, str]:
        result = await user_model.refresh_auth_token(refresh_token, access_token)
        return result.model_dump()

    @rpc_server.register("auth_get_user")
    async def get(
        keyword: str,
        criterion: Mapping[str, Any],
        limit: int,
        offset: int,
        user_token_data: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        result = await user_model.get(
            search_filter=SearchFilter(keyword=keyword, criterion=criterion),
            limit=limit,
            offset=offset,
        )
        return result.model_dump()

    @rpc_server.register("auth_get_user_by_id")
    async def get_by_id(
        id: str, user_token_data: Mapping[str, Any] = {}
    ) -> Mapping[str, Any]:
        row = await user_model.get_by_id(id)
        return row.model_dump()

    @rpc_server.register("auth_insert_user")
    async def insert(
        data: Mapping[str, Any], user_token_data: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        user_token_data = AccessTokenData(**user_token_data)
        data["created_by"] = user_token_data.user_id
        data["updated_by"] = user_token_data.user_id
        row = await user_model.insert(data=UserData(**data))
        return row.model_dump()

    @rpc_server.register("auth_update_user")
    async def update(
        id: str, data: Mapping[str, Any], user_token_data: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        user_token_data = AccessTokenData(**user_token_data)
        data["updated_by"] = user_token_data.user_id
        row = await user_model.update(id=id, data=UserData(**data))
        return row.model_dump()

    @rpc_server.register("auth_delete_user")
    async def delete(id: str, user_token_data: Mapping[str, Any]) -> Mapping[str, Any]:
        user_token_data = AccessTokenData(**user_token_data)
        row = await user_model.delete(id=id)
        return row.model_dump()
