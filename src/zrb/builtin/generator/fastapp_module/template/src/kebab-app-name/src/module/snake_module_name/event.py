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

    @consumer.register('hit_snake_module_name')
    async def hit_snake_module_name_event(message):
        logger.info(f'👋 Getting message: {message}')
