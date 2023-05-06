from fastapi import FastAPI
from logging import Logger
from core.messagebus import Publisher
from core.rpc import Caller
from module.auth.core import Authorizer
from module.auth.entity.permission.api import (
    register_api as register_permission_api
)
from module.auth.entity.group.api import (
    register_api as register_group_api
)
from module.auth.entity.user.api import (
    register_api as register_user_api,
    register_auth_api as register_user_login_api
)


def register_api(
    logger: Logger,
    app: FastAPI,
    authorizer: Authorizer,
    rpc_caller: Caller,
    publisher: Publisher
):
    logger.info('🥪 Register API for "auth"')
    register_user_login_api(logger, app, authorizer, rpc_caller, publisher)
    register_permission_api(logger, app, authorizer, rpc_caller, publisher)
    register_group_api(logger, app, authorizer, rpc_caller, publisher)
    register_user_api(logger, app, authorizer, rpc_caller, publisher)
