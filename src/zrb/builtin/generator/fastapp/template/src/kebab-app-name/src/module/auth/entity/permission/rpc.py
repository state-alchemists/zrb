from typing import Any, List
from logging import Logger
from core.messagebus import Publisher
from core.rpc import Caller, Server
from module.auth.component.model import permission_model
from module.auth.schema.permission import Permission


def register_rpc(
    logger: Logger,
    rpc_server: Server,
    rpc_caller: Caller,
    publisher: Publisher
):
    logger.info('🥪 Register RPC handlers for "auth.permission"')

    @rpc_server.register('get_permission')
    async def get(*args: Any, **kwargs: Any) -> List[Permission]:
        return {
            permission_model.get()
        }
