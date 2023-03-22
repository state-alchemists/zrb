from typing import Any, Callable, Mapping
from core.messagebus.messagebus import (
    Publisher, Consumer, MessageSerializer, THandler
)
import asyncio
import inspect
import logging


class MockConsumer(Consumer):
    def __init__(
        self, logger: logging.Logger, serializer: MessageSerializer
    ):
        self.logger = logger
        self.serializer = serializer
        self._handlers: Mapping[str, THandler] = {}

    def register(self, event_name: str) -> Callable[[THandler], Any]:
        def wrapper(handler: THandler):
            self.logger.warning(f'🪵 Register handler for "{event_name}"')
            self._handlers[event_name] = handler
            return handler
        return wrapper

    async def handle(self, event_name: str, encoded_value: Any):
        message_handler = self._handlers[event_name]
        decoded_value = self.serializer.decode(event_name, encoded_value)
        self.logger.info(f'🪵 Consume "{event_name}": {decoded_value}')
        if inspect.iscoroutinefunction(message_handler):
            return asyncio.create_task(message_handler(decoded_value))
        return message_handler(decoded_value)

    async def run(self):
        return


class MockPublisher(Publisher):
    def __init__(
        self,
        logger: logging.Logger,
        consumer: MockConsumer,
        serializer: MessageSerializer
    ):
        self.logger = logger
        self.consumer = consumer
        self.serializer = serializer

    async def publish(self, event_name: str, message: Any):
        encoded_value = self.serializer.encode(event_name, message)
        self.logger.info(f'🪵 Publish "{event_name}": {message}')
        await self.consumer.handle(event_name, encoded_value)
