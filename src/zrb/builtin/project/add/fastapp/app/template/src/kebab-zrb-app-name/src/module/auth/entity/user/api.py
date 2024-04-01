from logging import Logger
from typing import Annotated, List, Mapping

from component.error import HTTPAPIException
from component.messagebus import Publisher
from component.rpc import Caller
from fastapi import Depends, FastAPI
from fastapi.security import OAuth2PasswordRequestForm
from module.auth.component import Authorizer
from module.auth.integration import access_token_scheme, bearer_token_scheme
from module.auth.schema.request import IsAuthorizedRequest, RefreshTokenRequest
from module.auth.schema.token import AccessTokenData, TokenResponse
from module.auth.schema.user import User, UserData, UserLogin, UserResult
from opentelemetry import trace

tracer = trace.get_tracer(__name__)


def register_auth_api(
    logger: Logger,
    app: FastAPI,
    authorizer: Authorizer,
    rpc_caller: Caller,
    publisher: Publisher,
):
    logger.info('🥪 Register Login API for "auth.user"')

    @app.post("/api/v1/auth/login-oauth", response_model=TokenResponse)
    async def login_oauth(
        form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
    ) -> TokenResponse:
        data = UserLogin(identity=form_data.username, password=form_data.password)
        return await _create_token(data=data)

    @app.post("/api/v1/auth/login", response_model=TokenResponse)
    async def login(data: UserLogin) -> TokenResponse:
        return await _create_token(data=data)

    async def _create_token(data: UserLogin) -> TokenResponse:
        try:
            with tracer.start_as_current_span("auth.rpc.auth_create_token"):
                token_response_dict = await rpc_caller.call(
                    "auth_create_token", login_data=data.model_dump()
                )
                return TokenResponse(**token_response_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)

    @app.post("/api/v1/auth/refresh-token", response_model=TokenResponse)
    async def refresh_token(
        data: RefreshTokenRequest, refresh_token: str = Depends(bearer_token_scheme)
    ) -> TokenResponse:
        try:
            with tracer.start_as_current_span("auth.rpc.auth_refresh_token"):
                token_response_dict = await rpc_caller.call(
                    "auth_refresh_token",
                    refresh_token=refresh_token,
                    access_token=data.access_token,
                )
                return TokenResponse(**token_response_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)

    @app.post("/api/v1/auth/is-authorized", response_model=Mapping[str, bool])
    async def is_authorized(
        data: IsAuthorizedRequest,
        user_token_data: AccessTokenData = Depends(access_token_scheme),
    ) -> Mapping[str, str]:
        try:
            user_id = user_token_data.user_id
            with tracer.start_as_current_span("auth.rpc.auth_is_user_authorized"):
                return await rpc_caller.call(
                    "auth_is_user_authorized",
                    id=user_id,
                    permission_name=data.permission_names,
                )
        except Exception as e:
            raise HTTPAPIException(error=e)


def register_api(
    logger: Logger,
    app: FastAPI,
    authorizer: Authorizer,
    rpc_caller: Caller,
    publisher: Publisher,
):
    logger.info('🥪 Register API for "auth.user"')

    @app.get("/api/v1/auth/users", response_model=UserResult)
    async def get_users(
        keyword: str = "",
        limit: int = 100,
        offset: int = 0,
        user_token_data: AccessTokenData = Depends(access_token_scheme),
    ):
        with tracer.start_as_current_span("authorizer.is_having_permission"):
            if not await authorizer.is_having_permission(
                user_token_data.user_id, "auth:user:get"
            ):
                raise HTTPAPIException(403, "Unauthorized")
        try:
            with tracer.start_as_current_span("auth.rpc.auth_get_user"):
                result_dict = await rpc_caller.call(
                    "auth_get_user",
                    keyword=keyword,
                    criterion={},
                    limit=limit,
                    offset=offset,
                    user_token_data=user_token_data.model_dump(),
                )
                return UserResult(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)

    @app.get("/api/v1/auth/users/{id}", response_model=User)
    async def get_user_by_id(
        id: str, user_token_data: AccessTokenData = Depends(access_token_scheme)
    ):
        with tracer.start_as_current_span("authorizer.is_having_permission"):
            if not await authorizer.is_having_permission(
                user_token_data.user_id, "auth:user:get_by_id"
            ):
                raise HTTPAPIException(403, "Unauthorized")
        try:
            with tracer.start_as_current_span("auth.rpc.auth_get_user_by_id"):
                result_dict = await rpc_caller.call(
                    "auth_get_user_by_id",
                    id=id,
                    user_token_data=user_token_data.model_dump(),
                )
                return User(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)

    @app.post("/api/v1/auth/users", response_model=User)
    async def insert_user(
        data: UserData, user_token_data: AccessTokenData = Depends(access_token_scheme)
    ):
        with tracer.start_as_current_span("authorizer.is_having_permission"):
            if not await authorizer.is_having_permission(
                user_token_data.user_id, "auth:user:insert"
            ):
                raise HTTPAPIException(403, "Unauthorized")
        try:
            with tracer.start_as_current_span("auth.rpc.auth_insert_user"):
                result_dict = await rpc_caller.call(
                    "auth_insert_user",
                    data=data.model_dump(),
                    user_token_data=user_token_data.model_dump(),
                )
                return User(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)

    @app.put("/api/v1/auth/users/{id}", response_model=User)
    async def update_user(
        id: str,
        data: UserData,
        user_token_data: AccessTokenData = Depends(access_token_scheme),
    ):
        with tracer.start_as_current_span("authorizer.is_having_permission"):
            if not await authorizer.is_having_permission(
                user_token_data.user_id, "auth:user:update"
            ):
                raise HTTPAPIException(403, "Unauthorized")
        try:
            with tracer.start_as_current_span("auth.rpc.auth_update_user"):
                result_dict = await rpc_caller.call(
                    "auth_update_user",
                    id=id,
                    data=data.model_dump(),
                    user_token_data=user_token_data.model_dump(),
                )
                return User(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)

    @app.delete("/api/v1/auth/users/{id}", response_model=User)
    async def delete_user(
        id: str, user_token_data: AccessTokenData = Depends(access_token_scheme)
    ):
        with tracer.start_as_current_span("authorizer.is_having_permission"):
            if not await authorizer.is_having_permission(
                user_token_data.user_id, "auth:user:delete"
            ):
                raise HTTPAPIException(403, "Unauthorized")
        try:
            with tracer.start_as_current_span("auth.rpc.auth_delete_user"):
                result_dict = await rpc_caller.call(
                    "auth_delete_user",
                    id=id,
                    user_token_data=user_token_data.model_dump(),
                )
                return User(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)
