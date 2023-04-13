from logging import Logger
from core.messagebus.messagebus import Publisher, Consumer
from core.rpc.rpc import Caller


def register_event(
    logger: Logger,
    consumer: Consumer,
    rpc_caller: Caller,
    publisher: Publisher
):
    logger.info('🥪 Register event handlers for "auth"')

    @consumer.register('hit_auth')
    async def hit_auth_event(message):
        logger.info(f'👋 Get message: {message}')
