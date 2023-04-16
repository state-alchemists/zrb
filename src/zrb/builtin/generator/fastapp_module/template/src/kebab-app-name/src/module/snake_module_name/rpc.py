from typing import Any
from logging import Logger
from core.messagebus import Publisher
from core.rpc import Caller, Server


def register_rpc(
    logger: Logger,
    rpc_server: Server,
    rpc_caller: Caller,
    publisher: Publisher
):
    logger.info('🥪 Register RPC handlers for "snake_module_name"')

    @rpc_server.register('process_snake_module_name')
    async def process_snake_module_name(*args: Any, **kwargs: Any):
        return {
            'args': args, 'kwargs': kwargs
        }
