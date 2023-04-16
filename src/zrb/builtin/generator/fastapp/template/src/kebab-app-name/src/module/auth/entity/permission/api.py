from fastapi import FastAPI
from logging import Logger
from core.messagebus import Publisher
from core.rpc import Caller
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
        result_dict = await rpc_caller.call(
            'get_auth_permission',
            keyword=keyword,
            criterion={},
            limit=limit,
            offset=offset
        )
        return PermissionResult(**result_dict)

    @app.get(
        '/api/v1/auth/permissions/{id}', response_model=Permission
    )
    async def get_permission_by_id(id: str):
        result_dict = await rpc_caller.call(
            'get_auth_permission_by_id', id=id
        )
        return Permission(**result_dict)

    @app.post(
        '/api/v1/auth/permissions', response_model=Permission
    )
    async def insert_permission(data: PermissionData):
        result_dict = await rpc_caller.call(
            'insert_auth_permission', data=data.dict()
        )
        return Permission(**result_dict)

    @app.put(
        '/api/v1/auth/permissions/{id}', response_model=Permission
    )
    async def update_permission(id: str, data: PermissionData):
        result_dict = await rpc_caller.call(
            'update_auth_permission', id=id, data=data.dict()
        )
        return Permission(**result_dict)

    @app.delete(
        '/api/v1/auth/permissions/{id}', response_model=Permission
    )
    async def delete_permission(id: str):
        result_dict = await rpc_caller.call(
            'delete_auth_permission', id=id
        )
        return Permission(**result_dict)
