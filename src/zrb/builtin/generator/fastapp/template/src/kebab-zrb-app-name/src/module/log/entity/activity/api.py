from logging import Logger

from component.error import HTTPAPIException
from component.messagebus import Publisher
from component.rpc import Caller
from fastapi import Depends, FastAPI
from module.auth.component import Authorizer
from module.auth.integration import access_token_scheme
from module.auth.schema.token import AccessTokenData
from module.log.schema.activity import Activity, ActivityResult
from opentelemetry import trace

tracer = trace.get_tracer(__name__)


def register_api(
    logger: Logger,
    app: FastAPI,
    authorizer: Authorizer,
    rpc_caller: Caller,
    publisher: Publisher,
):
    logger.info('🥪 Register API for "log.activity"')

    @app.get("/api/v1/log/activities", response_model=ActivityResult)
    async def get_activitys(
        keyword: str = "",
        limit: int = 100,
        offset: int = 0,
        user_token_data: AccessTokenData = Depends(access_token_scheme),
    ):
        with tracer.start_as_current_span("authorizer.is_having_permission"):
            if not await authorizer.is_having_permission(
                user_token_data.user_id, "log:activity:get"
            ):
                raise HTTPAPIException(403, "Unauthorized")
        try:
            with tracer.start_as_current_span("log.rpc.log_get_activity"):
                result_dict = await rpc_caller.call(
                    "log_get_activity",
                    keyword=keyword,
                    criterion={},
                    limit=limit,
                    offset=offset,
                    user_token_data=user_token_data.model_dump(),
                )
                return ActivityResult(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)

    @app.get("/api/v1/log/activities/{id}", response_model=Activity)
    async def get_activity_by_id(
        id: str, user_token_data: AccessTokenData = Depends(access_token_scheme)
    ):
        with tracer.start_as_current_span("authorizer.is_having_permission"):
            if not await authorizer.is_having_permission(
                user_token_data.user_id, "log:activity:get_by_id"
            ):
                raise HTTPAPIException(403, "Unauthorized")
        try:
            with tracer.start_as_current_span("log.rpc.log_get_activity_by_id"):
                result_dict = await rpc_caller.call(
                    "log_get_activity_by_id",
                    id=id,
                    user_token_data=user_token_data.model_dump(),
                )
                return Activity(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)
