from config import (
    APP_ENABLE_API,
    APP_ENABLE_AUTH_MODULE,
    APP_ENABLE_EVENT_HANDLER,
    APP_ENABLE_RPC_SERVER,
)
from integration.app.app import app
from integration.log import logger
from integration.messagebus import consumer, publisher
from integration.rpc import rpc_caller, rpc_server
from module.auth.api import register_api
from module.auth.event import register_event
from module.auth.integration import authorizer
from module.auth.rpc import register_rpc


def register_auth():
    if not APP_ENABLE_AUTH_MODULE:
        logger.info('🥪 Skip registering "auth"')
        return
    if APP_ENABLE_API:
        register_api(
            logger=logger,
            app=app,
            authorizer=authorizer,
            rpc_caller=rpc_caller,
            publisher=publisher,
        )
    if APP_ENABLE_EVENT_HANDLER:
        register_event(
            logger=logger, consumer=consumer, rpc_caller=rpc_caller, publisher=publisher
        )
    if APP_ENABLE_RPC_SERVER:
        register_rpc(
            logger=logger,
            rpc_server=rpc_server,
            rpc_caller=rpc_caller,
            publisher=publisher,
        )
