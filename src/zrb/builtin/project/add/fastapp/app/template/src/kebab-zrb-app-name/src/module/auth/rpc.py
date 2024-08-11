from logging import Logger

from component.messagebus import Publisher
from component.rpc import Caller, Server
from module.auth.entity.group.rpc import register_rpc as register_group_rpc
from module.auth.entity.permission.rpc import register_rpc as register_permission_rpc
from module.auth.entity.user.rpc import register_rpc as register_user_rpc


def register_rpc(
    logger: Logger, rpc_server: Server, rpc_caller: Caller, publisher: Publisher
):
    logger.info('🥪 Register RPC handlers for "auth"')
    register_permission_rpc(logger, rpc_server, rpc_caller, publisher)
    register_group_rpc(logger, rpc_server, rpc_caller, publisher)
    register_user_rpc(logger, rpc_server, rpc_caller, publisher)
