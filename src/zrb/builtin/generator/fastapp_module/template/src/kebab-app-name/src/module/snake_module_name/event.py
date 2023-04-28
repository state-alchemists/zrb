from logging import Logger
from core.messagebus import Publisher, Consumer
from core.rpc import Caller


def register_event(
    logger: Logger,
    consumer: Consumer,
    rpc_caller: Caller,
    publisher: Publisher
):
    logger.info('🥪 Register event handlers for "snake_module_name"')
