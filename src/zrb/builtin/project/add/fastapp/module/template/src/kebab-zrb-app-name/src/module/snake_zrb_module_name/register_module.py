from config import (
    app_enable_api,
    app_enable_event_handler,
    app_enable_rpc_server,
    app_enable_snake_zrb_module_name_module,
)
from integration.app import app
from integration.log import logger
from integration.messagebus import consumer, publisher
from integration.rpc import rpc_caller, rpc_server
from module.auth.integration import authorizer
from module.snake_zrb_module_name.api import register_api
from module.snake_zrb_module_name.event import register_event
from module.snake_zrb_module_name.rpc import register_rpc


def register_snake_zrb_module_name():
    if not app_enable_snake_zrb_module_name_module:
        logger.info('🥪 Skip registering "snake_zrb_module_name"')
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
