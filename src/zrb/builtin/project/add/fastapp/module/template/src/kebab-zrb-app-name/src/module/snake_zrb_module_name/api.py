from logging import Logger

from component.messagebus import Publisher
from component.rpc import Caller
from fastapi import FastAPI
from module.auth.component import Authorizer


def register_api(
    logger: Logger,
    app: FastAPI,
    authorizer: Authorizer,
    rpc_caller: Caller,
    publisher: Publisher,
):
    logger.info('🥪 Register API for "snake_zrb_module_name"')
