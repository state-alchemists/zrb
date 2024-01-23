from logging import Logger

from core.error import HTTPAPIException
from core.messagebus import Publisher
from core.rpc import Caller
from fastapi import Depends, FastAPI
from module.auth.component import access_token_scheme
from module.auth.core import Authorizer
from module.auth.schema.token import AccessTokenData
from module.log.schema.activity import Activity, ActivityResult


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
        if not await authorizer.is_having_permission(
            user_token_data.user_id, "log:activity:get"
        ):
            raise HTTPAPIException(403, "Unauthorized")
        try:
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
        if not await authorizer.is_having_permission(
            user_token_data.user_id, "log:activity:get_by_id"
        ):
            raise HTTPAPIException(403, "Unauthorized")
        try:
            result_dict = await rpc_caller.call(
                "log_get_activity_by_id",
                id=id,
                user_token_data=user_token_data.model_dump(),
            )
            return Activity(**result_dict)
        except Exception as e:
            raise HTTPAPIException(error=e)
