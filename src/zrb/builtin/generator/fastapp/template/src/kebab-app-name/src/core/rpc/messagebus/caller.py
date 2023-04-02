from typing import Any, Callable
from core.messagebus.messagebus import Admin, Consumer, Publisher
from core.rpc.rpc import Caller, Message
import logging
import uuid
import asyncio


class MessagebusCaller(Caller):

    def __init__(
        self,
        logger: logging.Logger,
        admin: Admin,
        publisher: Publisher,
        consumer_factory: Callable[[], Consumer],
        timeout: float = 30,
        check_reply_interval: float = 0.1
    ):
        self.logger = logger
        self.admin = admin
        self.publisher = publisher
        self.consumer_factory = consumer_factory
        self.timeout = timeout
        self.check_reply_interval = check_reply_interval

    async def call(self, rpc_name: str, *args: Any, **kwargs: Any):
        random_uuid = str(uuid.uuid4())
        reply_event_name = f'reply_{rpc_name}_{random_uuid}'
        await self.admin.create_events([reply_event_name])
        reply_consumer = self.consumer_factory()
        is_reply_accepted = False
        result = None

        @reply_consumer.register(reply_event_name)
        async def consume_reply(message: Any):
            nonlocal result, is_reply_accepted
            result = message
            is_reply_accepted = True
            await reply_consumer.stop()

        try:
            task = asyncio.create_task(reply_consumer.start())
            await self.publisher.publish(
                rpc_name,
                Message(
                    reply_event=reply_event_name,
                    args=args,
                    kwargs=kwargs
                ).to_dict()
            )
            await asyncio.gather(task)
        except (asyncio.CancelledError, GeneratorExit, Exception) as e:
            await self._clean_up(reply_consumer, reply_event_name)
            raise e
        # Waiting for reply
        waiting_time = 0
        while not is_reply_accepted:
            waiting_time += self.check_reply_interval
            await asyncio.sleep(self.check_reply_interval)
            if waiting_time > self.timeout:
                self.logger.error(
                    ' '.join([
                        '🤙 [messagebus-rpc-caller]',
                        'Timeout while waiting for reply event',
                        f'{reply_event_name}'
                    ])
                )
                break
        await self._clean_up(reply_consumer, reply_event_name)
        # Return result or throw error
        if waiting_time > self.timeout:
            raise Exception(
                f'Timeout while waiting for reply event: {reply_event_name}'
            )
        self.logger.info(
            '🤙 [messagebus-rpc-caller] RPC ' +
            f'"{rpc_name}" returning result: {result}'
        )
        return result

    async def _clean_up(self, reply_consumer: Consumer, reply_event_name: str):
        try:
            await reply_consumer.stop()
        except (asyncio.CancelledError, GeneratorExit, Exception):
            self.logger.error('🤙 [messagebus-rpc-caller]', exc_info=True)
        try:
            await self.admin.delete_events([reply_event_name])
        except (asyncio.CancelledError, GeneratorExit, Exception):
            self.logger.error('🤙 [messagebus-rpc-caller]', exc_info=True)
