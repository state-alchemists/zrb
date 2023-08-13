from fastapi import FastAPI
from logging import Logger
from core.messagebus import Publisher
from core.rpc import Caller
from module.auth.core import Authorizer


def register_api(
    logger: Logger,
    app: FastAPI,
    authorizer: Authorizer,
    rpc_caller: Caller,
    publisher: Publisher
):
    logger.info('🥪 Register API for "snake_zrb_module_name"')
