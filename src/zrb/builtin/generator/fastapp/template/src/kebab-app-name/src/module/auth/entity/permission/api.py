from fastapi import FastAPI
from logging import Logger
from core.messagebus import Publisher
from core.rpc import Caller
from helper.error import get_http_api_error
from module.auth.schema.permission import (
    Permission, PermissionData, PermissionResult
)


def register_api(
    logger: Logger,
    app: FastAPI,
    rpc_caller: Caller,
    publisher: Publisher
):
    logger.info('🥪 Register API for "auth.permission"')

    @app.get(
        '/api/v1/auth/permissions', response_model=PermissionResult
    )
    async def get_permissions(
        keyword: str = '', limit: int = 100, offset: int = 0
    ):
        try:
            result_dict = await rpc_caller.call(
                'get_auth_permission',
                keyword=keyword,
                criterion={},
                limit=limit,
                offset=offset
            )
            return PermissionResult(**result_dict)
        except Exception as e:
            raise get_http_api_error(e)

    @app.get(
        '/api/v1/auth/permissions/{id}', response_model=Permission
    )
    async def get_permission_by_id(id: str):
        try:
            result_dict = await rpc_caller.call(
                'get_auth_permission_by_id', id=id
            )
            return Permission(**result_dict)
        except Exception as e:
            raise get_http_api_error(e)

    @app.post(
        '/api/v1/auth/permissions', response_model=Permission
    )
    async def insert_permission(data: PermissionData):
        try:
            result_dict = await rpc_caller.call(
                'insert_auth_permission', data=data.dict()
            )
            return Permission(**result_dict)
        except Exception as e:
            raise get_http_api_error(e)

    @app.put(
        '/api/v1/auth/permissions/{id}', response_model=Permission
    )
    async def update_permission(id: str, data: PermissionData):
        try:
            result_dict = await rpc_caller.call(
                'update_auth_permission', id=id, data=data.dict()
            )
            return Permission(**result_dict)
        except Exception as e:
            raise get_http_api_error(e)

    @app.delete(
        '/api/v1/auth/permissions/{id}', response_model=Permission
    )
    async def delete_permission(id: str):
        try:
            result_dict = await rpc_caller.call(
                'delete_auth_permission', id=id
            )
            return Permission(**result_dict)
        except Exception as e:
            raise get_http_api_error(e)
