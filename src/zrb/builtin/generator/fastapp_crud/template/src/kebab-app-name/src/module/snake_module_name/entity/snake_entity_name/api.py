from fastapi import FastAPI, Depends
from logging import Logger
from core.messagebus import Publisher
from core.rpc import Caller
from core.error import HTTPAPIException
from module.auth.core import Authorizer
from module.auth.schema.snake_entity_name import (
    PascalEntityName, PascalEntityNameData, PascalEntityNameResult
)
from module.auth.schema.token import TokenData
from module.auth.component import token_scheme


def register_api(
    logger: Logger,
    app: FastAPI,
    authorizer: Authorizer,
    rpc_caller: Caller,
    publisher: Publisher
):
    logger.info('🥪 Register API for "auth.snake_entity_name"')

    @app.get(
        '/api/v1/auth/snake_entity_names', response_model=PascalEntityNameResult
    )
    async def get_snake_entity_names(
        keyword: str = '', limit: int = 100, offset: int = 0,
        user_token_data: TokenData = Depends(token_scheme)
    ):
        if not await authorizer.is_having_snake_entity_name(
            user_token_data.user_id, 'auth:snake_entity_name:get'
        ):
            raise HTTPAPIException(403, 'Unauthorized')
        try:
            result_dict = await rpc_caller.call(
                'auth_get_snake_entity_name',
                keyword=keyword,
                criterion={},
                limit=limit,
                offset=offset,
                user_token_data=user_token_data.dict()
            )
            return PascalEntityNameResult(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)

    @app.get(
        '/api/v1/auth/snake_entity_names/{id}', response_model=PascalEntityName
    )
    async def get_snake_entity_name_by_id(
        id: str, user_token_data: TokenData = Depends(token_scheme)
    ):
        if not await authorizer.is_having_snake_entity_name(
            user_token_data.user_id, 'auth:snake_entity_name:get_by_id'
        ):
            raise HTTPAPIException(403, 'Unauthorized')
        try:
            result_dict = await rpc_caller.call(
                'auth_get_snake_entity_name_by_id',
                id=id, user_token_data=user_token_data.dict()
            )
            return PascalEntityName(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)

    @app.post(
        '/api/v1/auth/snake_entity_names', response_model=PascalEntityName
    )
    async def insert_snake_entity_name(
        data: PascalEntityNameData,
        user_token_data: TokenData = Depends(token_scheme)
    ):
        if not await authorizer.is_having_snake_entity_name(
            user_token_data.user_id, 'auth:snake_entity_name:insert'
        ):
            raise HTTPAPIException(403, 'Unauthorized')
        try:
            result_dict = await rpc_caller.call(
                'auth_insert_snake_entity_name',
                data=data.dict(), user_token_data=user_token_data.dict()
            )
            return PascalEntityName(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)

    @app.put(
        '/api/v1/auth/snake_entity_names/{id}', response_model=PascalEntityName
    )
    async def update_snake_entity_name(
        id: str, data: PascalEntityNameData,
        user_token_data: TokenData = Depends(token_scheme)
    ):
        if not await authorizer.is_having_snake_entity_name(
            user_token_data.user_id, 'auth:snake_entity_name:update'
        ):
            raise HTTPAPIException(403, 'Unauthorized')
        try:
            result_dict = await rpc_caller.call(
                'auth_update_snake_entity_name',
                id=id, data=data.dict(), user_token_data=user_token_data.dict()
            )
            return PascalEntityName(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)

    @app.delete(
        '/api/v1/auth/snake_entity_names/{id}', response_model=PascalEntityName
    )
    async def delete_snake_entity_name(
        id: str, user_token_data: TokenData = Depends(token_scheme)
    ):
        if not await authorizer.is_having_snake_entity_name(
            user_token_data.user_id, 'auth:snake_entity_name:delete'
        ):
            raise HTTPAPIException(403, 'Unauthorized')
        try:
            result_dict = await rpc_caller.call(
                'auth_delete_snake_entity_name',
                id=id, user_token_data=user_token_data.dict()
            )
            return PascalEntityName(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)
