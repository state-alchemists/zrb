from typing import Annotated
from fastapi import FastAPI, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from logging import Logger
from core.messagebus import Publisher
from core.rpc import Caller
from helper.error import get_http_api_error, create_http_api_exception
from module.auth.schema.user import (
    User, UserData, UserResult, UserLogin
)
from module.auth.schema.token import TokenResponse


def register_login_api(
    logger: Logger,
    app: FastAPI,
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
        except Exception:
            raise create_http_api_exception(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail='Incorrect identity or password',
                headers={"WWW-Authenticate": "Bearer"},
            )


def register_api(
    logger: Logger,
    app: FastAPI,
    rpc_caller: Caller,
    publisher: Publisher
):
    logger.info('🥪 Register API for "auth.user"')

    @app.get(
        '/api/v1/auth/users', response_model=UserResult
    )
    async def get_users(
        keyword: str = '', limit: int = 100, offset: int = 0
    ):
        try:
            result_dict = await rpc_caller.call(
                'get_auth_user',
                keyword=keyword,
                criterion={},
                limit=limit,
                offset=offset
            )
            return UserResult(**result_dict)
        except Exception as e:
            raise get_http_api_error(e)

    @app.get(
        '/api/v1/auth/users/{id}', response_model=User
    )
    async def get_user_by_id(id: str):
        try:
            result_dict = await rpc_caller.call(
                'get_auth_user_by_id', id=id
            )
            return User(**result_dict)
        except Exception as e:
            raise get_http_api_error(e)

    @app.post(
        '/api/v1/auth/users', response_model=User
    )
    async def insert_user(data: UserData):
        try:
            result_dict = await rpc_caller.call(
                'insert_auth_user', data=data.dict()
            )
            return User(**result_dict)
        except Exception as e:
            raise get_http_api_error(e)

    @app.put(
        '/api/v1/auth/users/{id}', response_model=User
    )
    async def update_user(id: str, data: UserData):
        try:
            result_dict = await rpc_caller.call(
                'update_auth_user', id=id, data=data.dict()
            )
            return User(**result_dict)
        except Exception as e:
            raise get_http_api_error(e)

    @app.delete(
        '/api/v1/auth/users/{id}', response_model=User
    )
    async def delete_user(id: str):
        try:
            result_dict = await rpc_caller.call(
                'delete_auth_user', id=id
            )
            return User(**result_dict)
        except Exception as e:
            raise get_http_api_error(e)
