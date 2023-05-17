from fastapi import FastAPI, Depends
from logging import Logger
from core.messagebus import Publisher
from core.rpc import Caller
from core.error import HTTPAPIException
from module.auth.core import Authorizer
from module.auth.schema.group import (
    Group, GroupData, GroupResult
)
from module.auth.schema.token import AccessTokenData
from module.auth.component import access_token_scheme


def register_api(
    logger: Logger,
    app: FastAPI,
    authorizer: Authorizer,
    rpc_caller: Caller,
    publisher: Publisher
):
    logger.info('🥪 Register API for "auth.group"')

    @app.get(
        '/api/v1/auth/groups', response_model=GroupResult
    )
    async def get_groups(
        keyword: str = '', limit: int = 100, offset: int = 0,
        user_token_data: AccessTokenData = Depends(access_token_scheme),
    ):
        if not await authorizer.is_having_permission(
            user_token_data.user_id, 'auth:permission:get'
        ):
            raise HTTPAPIException(403, 'Unauthorized')
        try:
            result_dict = await rpc_caller.call(
                'auth_get_group',
                keyword=keyword,
                criterion={},
                limit=limit,
                offset=offset,
                user_token_data=user_token_data.dict()
            )
            return GroupResult(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)

    @app.get(
        '/api/v1/auth/groups/{id}', response_model=Group
    )
    async def get_group_by_id(
        id: str, user_token_data: AccessTokenData = Depends(access_token_scheme)
    ):
        if not await authorizer.is_having_permission(
            user_token_data.user_id, 'auth:group:get_by_id'
        ):
            raise HTTPAPIException(403, 'Unauthorized')
        try:
            result_dict = await rpc_caller.call(
                'auth_get_group_by_id',
                id=id, user_token_data=user_token_data.dict()
            )
            return Group(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)

    @app.post(
        '/api/v1/auth/groups', response_model=Group
    )
    async def insert_group(
        data: GroupData,
        user_token_data: AccessTokenData = Depends(access_token_scheme)
    ):
        if not await authorizer.is_having_permission(
            user_token_data.user_id, 'auth:group:insert'
        ):
            raise HTTPAPIException(403, 'Unauthorized')
        try:
            result_dict = await rpc_caller.call(
                'auth_insert_group',
                data=data.dict(), user_token_data=user_token_data.dict()
            )
            return Group(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)

    @app.put(
        '/api/v1/auth/groups/{id}', response_model=Group
    )
    async def update_group(
        id: str, data: GroupData,
        user_token_data: AccessTokenData = Depends(access_token_scheme)
    ):
        if not await authorizer.is_having_permission(
            user_token_data.user_id, 'auth:group:update'
        ):
            raise HTTPAPIException(403, 'Unauthorized')
        try:
            result_dict = await rpc_caller.call(
                'auth_update_group',
                id=id, data=data.dict(), user_token_data=user_token_data.dict()
            )
            return Group(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)

    @app.delete(
        '/api/v1/auth/groups/{id}', response_model=Group
    )
    async def delete_group(
        id: str,
        user_token_data: AccessTokenData = Depends(access_token_scheme)
    ):
        if not await authorizer.is_having_permission(
            user_token_data.user_id, 'auth:group:delete'
        ):
            raise HTTPAPIException(403, 'Unauthorized')
        try:
            result_dict = await rpc_caller.call(
                'auth_delete_group',
                id=id, user_token_data=user_token_data.dict()
            )
            return Group(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)
