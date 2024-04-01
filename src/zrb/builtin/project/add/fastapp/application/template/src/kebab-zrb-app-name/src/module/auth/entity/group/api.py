from logging import Logger

from component.error import HTTPAPIException
from component.messagebus import Publisher
from component.rpc import Caller
from fastapi import Depends, FastAPI
from module.auth.component import Authorizer
from module.auth.integration import access_token_scheme
from module.auth.schema.group import Group, GroupData, GroupResult
from module.auth.schema.token import AccessTokenData
from opentelemetry import trace

tracer = trace.get_tracer(__name__)


def register_api(
    logger: Logger,
    app: FastAPI,
    authorizer: Authorizer,
    rpc_caller: Caller,
    publisher: Publisher,
):
    logger.info('🥪 Register API for "auth.group"')

    @app.get("/api/v1/auth/groups", response_model=GroupResult)
    async def get_groups(
        keyword: str = "",
        limit: int = 100,
        offset: int = 0,
        user_token_data: AccessTokenData = Depends(access_token_scheme),
    ):
        with tracer.start_as_current_span("authorizer.is_having_permission"):
            if not await authorizer.is_having_permission(
                user_token_data.user_id, "auth:permission:get"
            ):
                raise HTTPAPIException(403, "Unauthorized")
        try:
            with tracer.start_as_current_span("auth.rpc.auth_get_group"):
                result_dict = await rpc_caller.call(
                    "auth_get_group",
                    keyword=keyword,
                    criterion={},
                    limit=limit,
                    offset=offset,
                    user_token_data=user_token_data.model_dump(),
                )
                return GroupResult(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)

    @app.get("/api/v1/auth/groups/{id}", response_model=Group)
    async def get_group_by_id(
        id: str, user_token_data: AccessTokenData = Depends(access_token_scheme)
    ):
        with tracer.start_as_current_span("authorizer.is_having_permission"):
            if not await authorizer.is_having_permission(
                user_token_data.user_id, "auth:group:get_by_id"
            ):
                raise HTTPAPIException(403, "Unauthorized")
        try:
            with tracer.start_as_current_span("auth.rpc.auth_get_group_by_id"):
                result_dict = await rpc_caller.call(
                    "auth_get_group_by_id",
                    id=id,
                    user_token_data=user_token_data.model_dump(),
                )
                return Group(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)

    @app.post("/api/v1/auth/groups", response_model=Group)
    async def insert_group(
        data: GroupData, user_token_data: AccessTokenData = Depends(access_token_scheme)
    ):
        with tracer.start_as_current_span("authorizer.is_having_permission"):
            if not await authorizer.is_having_permission(
                user_token_data.user_id, "auth:group:insert"
            ):
                raise HTTPAPIException(403, "Unauthorized")
        try:
            with tracer.start_as_current_span("auth.rpc.auth_insert_group"):
                result_dict = await rpc_caller.call(
                    "auth_insert_group",
                    data=data.model_dump(),
                    user_token_data=user_token_data.model_dump(),
                )
                return Group(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)

    @app.put("/api/v1/auth/groups/{id}", response_model=Group)
    async def update_group(
        id: str,
        data: GroupData,
        user_token_data: AccessTokenData = Depends(access_token_scheme),
    ):
        with tracer.start_as_current_span("authorizer.is_having_permission"):
            if not await authorizer.is_having_permission(
                user_token_data.user_id, "auth:group:update"
            ):
                raise HTTPAPIException(403, "Unauthorized")
        try:
            with tracer.start_as_current_span("auth.rpc.auth_update_group"):
                result_dict = await rpc_caller.call(
                    "auth_update_group",
                    id=id,
                    data=data.model_dump(),
                    user_token_data=user_token_data.model_dump(),
                )
                return Group(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)

    @app.delete("/api/v1/auth/groups/{id}", response_model=Group)
    async def delete_group(
        id: str, user_token_data: AccessTokenData = Depends(access_token_scheme)
    ):
        with tracer.start_as_current_span("authorizer.is_having_permission"):
            if not await authorizer.is_having_permission(
                user_token_data.user_id, "auth:group:delete"
            ):
                raise HTTPAPIException(403, "Unauthorized")
        try:
            with tracer.start_as_current_span("auth.rpc.auth_delete_group"):
                result_dict = await rpc_caller.call(
                    "auth_delete_group",
                    id=id,
                    user_token_data=user_token_data.model_dump(),
                )
                return Group(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)
