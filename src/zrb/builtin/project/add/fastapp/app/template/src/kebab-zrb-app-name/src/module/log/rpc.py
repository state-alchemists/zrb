from logging import Logger
from typing import Any

from component.messagebus import Publisher
from component.rpc import Caller, Server
from module.log.entity.activity.rpc import register_rpc as register_activity_rpc


def register_rpc(
    logger: Logger, rpc_server: Server, rpc_caller: Caller, publisher: Publisher
):
    logger.info('🥪 Register RPC handlers for "log"')
    register_activity_rpc(logger, rpc_server, rpc_caller, publisher)
