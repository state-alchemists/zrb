from typing import Annotated
from fastapi import FastAPI, Depends
from fastapi.security import OAuth2PasswordRequestForm
from logging import Logger
from core.messagebus import Publisher
from core.rpc import Caller
from core.error import HTTPAPIException
from module.auth.core import Authorizer
from module.auth.schema.user import (
    User, UserData, UserResult, UserLogin
)
from module.auth.schema.token import TokenData, TokenResponse
from module.auth.component import token_scheme


def register_login_api(
    logger: Logger,
    app: FastAPI,
    authorizer: Authorizer,
    rpc_caller: Caller,
    publisher: Publisher
):
    logger.info('🥪 Register Login API for "auth.user"')

    @app.post('/api/v1/login-oauth', response_model=TokenResponse)
    async def login_oauth(
        form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
    ) -> TokenResponse:
        data = UserLogin(
            identity=form_data.username,
            password=form_data.password
        )
        return await _login(data=data)

    @app.post('/api/v1/login', response_model=TokenResponse)
    async def login(data: UserLogin) -> TokenResponse:
        return await _login(data=data)

    async def _login(data: UserLogin) -> TokenResponse:
        try:
            token = await rpc_caller.call(
                'auth_login', login_data=data.dict()
            )
            return TokenResponse(access_token=token, token_type='bearer')
        except Exception as e:
            raise HTTPAPIException(error=e)


def register_api(
    logger: Logger,
    app: FastAPI,
    authorizer: Authorizer,
    rpc_caller: Caller,
    publisher: Publisher
):
    logger.info('🥪 Register API for "auth.user"')

    @app.get(
        '/api/v1/auth/users', response_model=UserResult
    )
    async def get_users(
        keyword: str = '', limit: int = 100, offset: int = 0,
        user_token_data: TokenData = Depends(token_scheme)
    ):
        if not await authorizer.is_having_permission(
            user_token_data.user_id, 'auth:user:get'
        ):
            raise HTTPAPIException(403, 'Unauthorized')
        try:
            result_dict = await rpc_caller.call(
                'auth_get_user',
                keyword=keyword,
                criterion={},
                limit=limit,
                offset=offset,
                user_token_data=user_token_data.dict()
            )
            return UserResult(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)

    @app.get(
        '/api/v1/auth/users/{id}', response_model=User
    )
    async def get_user_by_id(
        id: str, user_token_data: TokenData = Depends(token_scheme)
    ):
        if not await authorizer.is_having_permission(
            user_token_data.user_id, 'auth:user:get_by_id'
        ):
            raise HTTPAPIException(403, 'Unauthorized')
        try:
            result_dict = await rpc_caller.call(
                'auth_get_user_by_id',
                id=id, user_token_data=user_token_data.dict()
            )
            return User(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)

    @app.post(
        '/api/v1/auth/users', response_model=User
    )
    async def insert_user(
        data: UserData, user_token_data: TokenData = Depends(token_scheme)
    ):
        if not await authorizer.is_having_permission(
            user_token_data.user_id, 'auth:user:insert'
        ):
            raise HTTPAPIException(403, 'Unauthorized')
        try:
            result_dict = await rpc_caller.call(
                'auth_insert_user',
                data=data.dict(), user_token_data=user_token_data.dict()
            )
            return User(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)

    @app.put(
        '/api/v1/auth/users/{id}', response_model=User
    )
    async def update_user(
        id: str, data: UserData,
        user_token_data: TokenData = Depends(token_scheme)
    ):
        if not await authorizer.is_having_permission(
            user_token_data.user_id, 'auth:user:update'
        ):
            raise HTTPAPIException(403, 'Unauthorized')
        try:
            result_dict = await rpc_caller.call(
                'auth_update_user',
                id=id, data=data.dict(), user_token_data=user_token_data.dict()
            )
            return User(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)

    @app.delete(
        '/api/v1/auth/users/{id}', response_model=User
    )
    async def delete_user(
        id: str, user_token_data: TokenData = Depends(token_scheme)
    ):
        if not await authorizer.is_having_permission(
            user_token_data.user_id, 'auth:user:delete'
        ):
            raise HTTPAPIException(403, 'Unauthorized')
        try:
            result_dict = await rpc_caller.call(
                'auth_delete_user',
                id=id, user_token_data=user_token_data.dict()
            )
            return User(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)
