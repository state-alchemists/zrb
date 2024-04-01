from config import (
    app_enable_api,
    app_enable_event_handler,
    app_enable_log_module,
    app_enable_rpc_server,
)
from integration.app import app
from integration.log import logger
from integration.messagebus import consumer, publisher
from integration.rpc import rpc_caller, rpc_server
from module.auth.integration import authorizer
from module.log.api import register_api
from module.log.event import register_event
from module.log.rpc import register_rpc


def register_log():
    if not app_enable_log_module:
        logger.info('🥪 Skip registering "log"')
        return
    if app_enable_api:
        register_api(
            logger=logger,
            app=app,
            authorizer=authorizer,
            rpc_caller=rpc_caller,
            publisher=publisher,
        )
    if app_enable_event_handler:
        register_event(
            logger=logger, consumer=consumer, rpc_caller=rpc_caller, publisher=publisher
        )
    if app_enable_rpc_server:
        register_rpc(
            logger=logger,
            rpc_server=rpc_server,
            rpc_caller=rpc_caller,
            publisher=publisher,
        )
