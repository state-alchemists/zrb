from fastapi import FastAPI
from logging import Logger
from core.messagebus import Publisher
from core.rpc import Caller
from module.auth.entity.permission.api import (
    register_api as register_permission_api
)


def register_api(
    logger: Logger,
    app: FastAPI,
    rpc_caller: Caller,
    publisher: Publisher
):
    logger.info('🥪 Register API for "auth"')
    register_permission_api(logger, app, rpc_caller, publisher)
