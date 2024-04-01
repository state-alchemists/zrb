from logging import Logger

from component.messagebus import Consumer, Publisher
from component.rpc import Caller


def register_event(
    logger: Logger, consumer: Consumer, rpc_caller: Caller, publisher: Publisher
):
    logger.info('🥪 Register event handlers for "auth"')
