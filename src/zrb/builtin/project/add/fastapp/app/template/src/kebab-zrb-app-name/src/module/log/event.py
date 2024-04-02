from logging import Logger

from component.messagebus import Consumer, Publisher
from component.rpc import Caller
from module.log.entity.activity.event import register_event as register_activity_event


def register_event(
    logger: Logger, consumer: Consumer, rpc_caller: Caller, publisher: Publisher
):
    logger.info('🥪 Register event handlers for "log"')
    register_activity_event(logger, consumer, rpc_caller, publisher)
