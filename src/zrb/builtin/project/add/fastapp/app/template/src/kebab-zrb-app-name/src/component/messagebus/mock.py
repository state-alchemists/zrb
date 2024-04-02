import asyncio
import inspect
import logging
from typing import Any, Callable, List, Mapping

from component.messagebus.messagebus import (
    Admin,
    Consumer,
    MessageSerializer,
    Publisher,
    TEventHandler,
)


class MockConsumer(Consumer):
    def __init__(self, logger: logging.Logger, serializer: MessageSerializer):
        self.logger = logger
        self.serializer = serializer
        self._handlers: Mapping[str, TEventHandler] = {}

    def register(self, event_name: str) -> Callable[[TEventHandler], Any]:
        def wrapper(handler: TEventHandler):
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

    async def start(self):
        return

    async def stop(self):
        return


class MockPublisher(Publisher):
    def __init__(
        self,
        logger: logging.Logger,
        consumer: MockConsumer,
        serializer: MessageSerializer,
    ):
        self.logger = logger
        self.consumer = consumer
        self.serializer = serializer

    async def publish(self, event_name: str, message: Any):
        encoded_value = self.serializer.encode(event_name, message)
        self.logger.info(f'🪵 Publish "{event_name}": {message}')
        await self.consumer.handle(event_name, encoded_value)


class MockAdmin(Admin):
    async def create_events(self, event_names: List[str]):
        return

    async def delete_events(self, event_names: List[str]):
        return
