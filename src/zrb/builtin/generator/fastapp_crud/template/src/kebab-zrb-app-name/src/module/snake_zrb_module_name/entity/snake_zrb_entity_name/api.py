from fastapi import FastAPI, Depends
from logging import Logger
from core.messagebus import Publisher
from core.rpc import Caller
from core.error import HTTPAPIException
from module.auth.core import Authorizer
from module.snake_zrb_module_name.schema.snake_zrb_entity_name import (
    PascalZrbEntityName, PascalZrbEntityNameData, PascalZrbEntityNameResult
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
    logger.info('🥪 Register API for "snake_zrb_module_name.snake_zrb_entity_name"')

    @app.get(
        '/api/v1/kebab-zrb-module-name/kebab-zrb-plural-entity-name', response_model=PascalZrbEntityNameResult
    )
    async def get_snake_zrb_entity_names(
        keyword: str = '', limit: int = 100, offset: int = 0,
        user_token_data: AccessTokenData = Depends(access_token_scheme)
    ):
        if not await authorizer.is_having_permission(
            user_token_data.user_id, 'snake_zrb_module_name:snake_zrb_entity_name:get'
        ):
            raise HTTPAPIException(403, 'Unauthorized')
        try:
            result_dict = await rpc_caller.call(
                'snake_zrb_module_name_get_snake_zrb_entity_name',
                keyword=keyword,
                criterion={},
                limit=limit,
                offset=offset,
                user_token_data=user_token_data.dict()
            )
            return PascalZrbEntityNameResult(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)

    @app.get(
        '/api/v1/kebab-zrb-module-name/kebab-zrb-plural-entity-name/{id}', response_model=PascalZrbEntityName
    )
    async def get_snake_zrb_entity_name_by_id(
        id: str,
        user_token_data: AccessTokenData = Depends(access_token_scheme)
    ):
        if not await authorizer.is_having_permission(
            user_token_data.user_id, 'snake_zrb_module_name:snake_zrb_entity_name:get_by_id'
        ):
            raise HTTPAPIException(403, 'Unauthorized')
        try:
            result_dict = await rpc_caller.call(
                'snake_zrb_module_name_get_snake_zrb_entity_name_by_id',
                id=id, user_token_data=user_token_data.dict()
            )
            return PascalZrbEntityName(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)

    @app.post(
        '/api/v1/kebab-zrb-module-name/kebab-zrb-plural-entity-name', response_model=PascalZrbEntityName
    )
    async def insert_snake_zrb_entity_name(
        data: PascalZrbEntityNameData,
        user_token_data: AccessTokenData = Depends(access_token_scheme)
    ):
        if not await authorizer.is_having_permission(
            user_token_data.user_id, 'snake_zrb_module_name:snake_zrb_entity_name:insert'
        ):
            raise HTTPAPIException(403, 'Unauthorized')
        try:
            result_dict = await rpc_caller.call(
                'snake_zrb_module_name_insert_snake_zrb_entity_name',
                data=data.dict(), user_token_data=user_token_data.dict()
            )
            return PascalZrbEntityName(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)

    @app.put(
        '/api/v1/kebab-zrb-module-name/kebab-zrb-plural-entity-name/{id}', response_model=PascalZrbEntityName
    )
    async def update_snake_zrb_entity_name(
        id: str, data: PascalZrbEntityNameData,
        user_token_data: AccessTokenData = Depends(access_token_scheme)
    ):
        if not await authorizer.is_having_permission(
            user_token_data.user_id, 'snake_zrb_module_name:snake_zrb_entity_name:update'
        ):
            raise HTTPAPIException(403, 'Unauthorized')
        try:
            result_dict = await rpc_caller.call(
                'snake_zrb_module_name_update_snake_zrb_entity_name',
                id=id, data=data.dict(), user_token_data=user_token_data.dict()
            )
            return PascalZrbEntityName(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)

    @app.delete(
        '/api/v1/kebab-zrb-module-name/kebab-zrb-plural-entity-name/{id}', response_model=PascalZrbEntityName
    )
    async def delete_snake_zrb_entity_name(
        id: str,
        user_token_data: AccessTokenData = Depends(access_token_scheme)
    ):
        if not await authorizer.is_having_permission(
            user_token_data.user_id, 'snake_zrb_module_name:snake_zrb_entity_name:delete'
        ):
            raise HTTPAPIException(403, 'Unauthorized')
        try:
            result_dict = await rpc_caller.call(
                'snake_zrb_module_name_delete_snake_zrb_entity_name',
                id=id, user_token_data=user_token_data.dict()
            )
            return PascalZrbEntityName(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)
