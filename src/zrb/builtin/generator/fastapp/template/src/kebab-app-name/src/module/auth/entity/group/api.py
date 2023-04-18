from fastapi import FastAPI
from logging import Logger
from core.messagebus import Publisher
from core.rpc import Caller
from helper.error import get_http_api_error
from module.auth.schema.group import (
    Group, GroupData, GroupResult
)


def register_api(
    logger: Logger,
    app: FastAPI,
    rpc_caller: Caller,
    publisher: Publisher
):
    logger.info('🥪 Register API for "auth.group"')

    @app.get(
        '/api/v1/auth/groups', response_model=GroupResult
    )
    async def get_groups(
        keyword: str = '', limit: int = 100, offset: int = 0
    ):
        try:
            result_dict = await rpc_caller.call(
                'get_auth_group',
                keyword=keyword,
                criterion={},
                limit=limit,
                offset=offset
            )
            return GroupResult(**result_dict)
        except Exception as e:
            raise get_http_api_error(e)

    @app.get(
        '/api/v1/auth/groups/{id}', response_model=Group
    )
    async def get_group_by_id(id: str):
        try:
            result_dict = await rpc_caller.call(
                'get_auth_group_by_id', id=id
            )
            return Group(**result_dict)
        except Exception as e:
            raise get_http_api_error(e)

    @app.post(
        '/api/v1/auth/groups', response_model=Group
    )
    async def insert_group(data: GroupData):
        try:
            result_dict = await rpc_caller.call(
                'insert_auth_group', data=data.dict()
            )
            return Group(**result_dict)
        except Exception as e:
            raise get_http_api_error(e)

    @app.put(
        '/api/v1/auth/groups/{id}', response_model=Group
    )
    async def update_group(id: str, data: GroupData):
        try:
            result_dict = await rpc_caller.call(
                'update_auth_group', id=id, data=data.dict()
            )
            return Group(**result_dict)
        except Exception as e:
            raise get_http_api_error(e)

    @app.delete(
        '/api/v1/auth/groups/{id}', response_model=Group
    )
    async def delete_group(id: str):
        try:
            result_dict = await rpc_caller.call(
                'delete_auth_group', id=id
            )
            return Group(**result_dict)
        except Exception as e:
            raise get_http_api_error(e)
