from fastapi import FastAPI
from logging import Logger
from core.messagebus import Publisher
from core.rpc import Caller
from module.auth.core import Authorizer
from module.log.entity.activity.api import (
    register_api as register_activity_api
)


def register_api(
    logger: Logger,
    app: FastAPI,
    authorizer: Authorizer,
    rpc_caller: Caller,
    publisher: Publisher
):
    logger.info('🥪 Register API for "log"')
    register_activity_api(logger, app, authorizer, rpc_caller, publisher)
