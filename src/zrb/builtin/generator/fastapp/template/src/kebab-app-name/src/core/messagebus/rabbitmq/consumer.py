from typing import Any, Callable, Mapping, Optional
from core.messagebus.messagebus import (
    Consumer, TEventHandler, MessageSerializer, must_get_message_serializer
)
from core.messagebus.rabbitmq.admin import (
    RMQAdmin, must_get_rmq_admin
)
import asyncio
import aiormq
import inspect
import logging


class RMQConsumer(Consumer):
    def __init__(
        self,
        logger: logging.Logger,
        connection_string: str,
        serializer: Optional[MessageSerializer] = None,
        rmq_admin: Optional[RMQAdmin] = None,
        retry: int = 5,
        retry_interval: int = 5
    ):
        self.logger = logger
        self.rmq_admin = must_get_rmq_admin(
            logger=logger,
            rmq_admin=rmq_admin,
            connection_string=connection_string
        )
        self.connection_string = connection_string
        self.connection: Optional[aiormq.Connection] = None
        self.serializer = must_get_message_serializer(serializer)
        self.retry = retry
        self.retry_interval = retry_interval
        self._handlers: Mapping[str, TEventHandler] = {}
        self._is_start_triggered = False
        self._is_stop_triggered = False

    def register(self, event_name: str) -> Callable[[TEventHandler], Any]:
        def wrapper(handler: TEventHandler):
            self.logger.warning(f'🐰 Register handler for "{event_name}"')
            self._handlers[event_name] = handler
            return handler
        return wrapper

    async def start(self):
        if self._is_start_triggered:
            return
        self._is_start_triggered = True
        return await self._start(self.retry)

    async def stop(self):
        if self._is_stop_triggered:
            return
        self._is_stop_triggered = True
        await self._disconnect()

    async def _start(self, retry: int):
        try:
            if self.connection is None or self.connection.is_closed:
                await self._connect()
            self.logger.info('🐰 Get channel')
            channel = await self.connection.channel()
            event_names = list(self._handlers.keys())
            await self.rmq_admin.create_events(event_names)
            for event_name in event_names:
                queue_name = self.rmq_admin.get_queue_name(event_name)
                on_message = self._create_consumer_callback(
                    channel, event_name
                )
                await channel.basic_consume(
                    queue=queue_name, consumer_callback=on_message
                )
            retry = self.retry
            while True:
                await asyncio.sleep(0.01)
        except Exception:
            if retry == 0:
                self.logger.error(
                    f'🐰 Failed to consume message after {self.retry} attempts'
                )
                raise
            await self._disconnect()
            await asyncio.sleep(self.retry_interval)
            await self._start(retry-1)
        finally:
            await self._disconnect()

    async def _connect(self):
        self.logger.info('🐰 Create consumer connection')
        self.connection = await aiormq.connect(self.connection_string)
        self.logger.info('🐰 Consumer connection created')

    async def _disconnect(self):
        self.logger.info('🐰 Close consumer connection')
        if self.connection is not None:
            await self.connection.close()
        self.logger.info('🐰 Consumer connection closed')
        self.connection = None

    def _create_consumer_callback(
        self,
        channel: aiormq.Channel,
        event_name: str,
    ) -> Callable[[Any], Any]:
        async def on_message(message):
            decoded_value = self.serializer.decode(event_name, message.body)
            handler = self._handlers.get(event_name)
            queue_name = self.rmq_admin.get_queue_name(event_name)
            self.logger.info(f'🐰 Consume from "{queue_name}": {decoded_value}')
            await self._run_handler(handler, decoded_value)
            await channel.basic_ack(message.delivery_tag)
        return on_message

    async def _run_handler(
        self, message_handler: TEventHandler, decoded_value: Any
    ):
        if inspect.iscoroutinefunction(message_handler):
            return asyncio.create_task(message_handler(decoded_value))
        return message_handler(decoded_value)
