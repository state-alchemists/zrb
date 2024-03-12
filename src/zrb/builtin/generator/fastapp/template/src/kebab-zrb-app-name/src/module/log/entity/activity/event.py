from logging import Logger
from typing import Any, Mapping

from component.messagebus import Consumer, Publisher
from component.rpc import Caller
from module.log.integration.model.activity_model import activity_model
from module.log.schema.activity import ActivityData


def register_event(
    logger: Logger, consumer: Consumer, rpc_caller: Caller, publisher: Publisher
):
    logger.info('🥪 Register event handlers for "log.activity"')

    @consumer.register("log_new_activity")
    async def insert(data: Mapping[str, Any]):
        await activity_model.insert(data=ActivityData(**data))
