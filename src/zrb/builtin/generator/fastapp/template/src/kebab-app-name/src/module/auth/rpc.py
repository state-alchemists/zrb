from typing import Any
from logging import Logger
from core.messagebus import Publisher
from core.rpc import Caller, Server
from module.auth.entity.permission.rpc import (
    register_rpc as register_permission_rpc
)


def register_rpc(
    logger: Logger,
    rpc_server: Server,
    rpc_caller: Caller,
    publisher: Publisher
):
    logger.info('🥪 Register RPC handlers for "auth"')

    @rpc_server.register('process_auth')
    async def process_auth(*args: Any, **kwargs: Any):
        return {
            'args': args, 'kwargs': kwargs
        }

    register_permission_rpc(logger, rpc_server, rpc_caller, publisher)
