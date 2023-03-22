from typing import Any, Callable, Mapping, Optional
from core.messagebus.messagebus import (
    Consumer, THandler, MessageSerializer, get_message_serializer
)
import asyncio
import aiormq
import inspect
import logging


class RMQConsumeConnection():
    def __init__(self, logger: logging.Logger, connection_string: str):
        self.logger = logger
        self.connection_string = connection_string
        self.connection: Optional[aiormq.Connection] = None

    async def __aenter__(self):
        self.logger.info('🐰 Create consumer connection')
        self.connection = await aiormq.connect(self.connection_string)
        self.logger.info('🐰 Consumer connection created')
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.logger.info('🐰 Close consumer connection')
        await self.connection.close()
        self.logger.info('🐰 Consumer connection closed')


class RMQConsumer(Consumer):
    def __init__(
        self,
        logger: logging.Logger,
        consume_connection: RMQConsumeConnection,
        serializer: Optional[MessageSerializer] = None,
        retry: int = 5
    ):
        self.logger = logger
        self.conn = consume_connection
        self._handlers: Mapping[str, THandler] = {}
        self.serializer = get_message_serializer(serializer)
        self._retry = retry

    def register(self, event_name: str) -> Callable[[THandler], Any]:
        def wrapper(handler: THandler):
            self.logger.warning(f'🐰 Register handler for "{event_name}"')
            self._handlers[event_name] = handler
            return handler
        return wrapper

    async def run(self):
        return await self._run(self._retry)

    async def _run(self, retry: int):
        try:
            async with self.conn as conn:
                connection: aiormq.Connection = conn.connection
                self.logger.info('🐰 Get channel')
                channel = await connection.channel()
                for event_name, handler in self._handlers.items():
                    self.logger.info(f'🐰 Declare queue: {event_name}')
                    await channel.queue_declare(event_name)
                    on_message = self._create_consumer_callback(
                        channel, event_name
                    )
                    asyncio.create_task(channel.basic_consume(
                        queue=event_name, consumer_callback=on_message
                    ))
            retry = self._retry
        except Exception:
            if retry == 0:
                raise
            await self._run(retry-1)

    def _create_consumer_callback(
        self,
        channel: aiormq.Channel,
        event_name: str,
    ) -> Callable[[Any], Any]:
        async def on_message(message):
            decoded_value = self.serializer.decode(event_name, message.body)
            handler = self._handlers.get(event_name)
            self.logger.info(f'🐰 Consume "{event_name}": {decoded_value}')
            await self._run_handler(handler, decoded_value)
            await channel.basic_ack(message.delivery_tag)
        return on_message

    async def _run_handler(
        self, message_handler: THandler, decoded_value: Any
    ):
        if inspect.iscoroutinefunction(message_handler):
            return asyncio.create_task(message_handler(decoded_value))
        return message_handler(decoded_value)
