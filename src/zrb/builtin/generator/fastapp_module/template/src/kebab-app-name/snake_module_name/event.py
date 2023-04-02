from logging import Logger
from core.messagebus.messagebus import Publisher, Consumer
from core.rpc.rpc import Caller


def register_event(
    logger: Logger,
    consumer: Consumer,
    rpc_caller: Caller,
    publisher: Publisher
):

    @consumer.register('hit_snake_module_name')
    async def hit_snake_module_name_event(message):
        logger.info(message)
