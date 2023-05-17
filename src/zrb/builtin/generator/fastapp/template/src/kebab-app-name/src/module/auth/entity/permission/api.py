from fastapi import FastAPI, Depends
from logging import Logger
from core.messagebus import Publisher
from core.rpc import Caller
from core.error import HTTPAPIException
from module.auth.core import Authorizer
from module.auth.schema.permission import (
    Permission, PermissionData, PermissionResult
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
    logger.info('🥪 Register API for "auth.permission"')

    @app.get(
        '/api/v1/auth/permissions', response_model=PermissionResult
    )
    async def get_permissions(
        keyword: str = '', limit: int = 100, offset: int = 0,
        user_token_data: AccessTokenData = Depends(access_token_scheme)
    ):
        if not await authorizer.is_having_permission(
            user_token_data.user_id, 'auth:permission:get'
        ):
            raise HTTPAPIException(403, 'Unauthorized')
        try:
            result_dict = await rpc_caller.call(
                'auth_get_permission',
                keyword=keyword,
                criterion={},
                limit=limit,
                offset=offset,
                user_token_data=user_token_data.dict()
            )
            return PermissionResult(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)

    @app.get(
        '/api/v1/auth/permissions/{id}', response_model=Permission
    )
    async def get_permission_by_id(
        id: str,
        user_token_data: AccessTokenData = Depends(access_token_scheme)
    ):
        if not await authorizer.is_having_permission(
            user_token_data.user_id, 'auth:permission:get_by_id'
        ):
            raise HTTPAPIException(403, 'Unauthorized')
        try:
            result_dict = await rpc_caller.call(
                'auth_get_permission_by_id',
                id=id, user_token_data=user_token_data.dict()
            )
            return Permission(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)

    @app.post(
        '/api/v1/auth/permissions', response_model=Permission
    )
    async def insert_permission(
        data: PermissionData,
        user_token_data: AccessTokenData = Depends(access_token_scheme)
    ):
        if not await authorizer.is_having_permission(
            user_token_data.user_id, 'auth:permission:insert'
        ):
            raise HTTPAPIException(403, 'Unauthorized')
        try:
            result_dict = await rpc_caller.call(
                'auth_insert_permission',
                data=data.dict(), user_token_data=user_token_data.dict()
            )
            return Permission(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)

    @app.put(
        '/api/v1/auth/permissions/{id}', response_model=Permission
    )
    async def update_permission(
        id: str, data: PermissionData,
        user_token_data: AccessTokenData = Depends(access_token_scheme)
    ):
        if not await authorizer.is_having_permission(
            user_token_data.user_id, 'auth:permission:update'
        ):
            raise HTTPAPIException(403, 'Unauthorized')
        try:
            result_dict = await rpc_caller.call(
                'auth_update_permission',
                id=id, data=data.dict(), user_token_data=user_token_data.dict()
            )
            return Permission(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)

    @app.delete(
        '/api/v1/auth/permissions/{id}', response_model=Permission
    )
    async def delete_permission(
        id: str,
        user_token_data: AccessTokenData = Depends(access_token_scheme)
    ):
        if not await authorizer.is_having_permission(
            user_token_data.user_id, 'auth:permission:delete'
        ):
            raise HTTPAPIException(403, 'Unauthorized')
        try:
            result_dict = await rpc_caller.call(
                'auth_delete_permission',
                id=id, user_token_data=user_token_data.dict()
            )
            return Permission(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)
