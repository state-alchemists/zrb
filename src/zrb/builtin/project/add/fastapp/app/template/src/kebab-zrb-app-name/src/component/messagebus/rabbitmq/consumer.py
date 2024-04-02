import asyncio
import inspect
import logging
from typing import Any, Callable, Mapping, Optional

import aiormq
from component.messagebus.messagebus import (
    Consumer,
    MessageSerializer,
    TEventHandler,
    must_get_message_serializer,
)
from component.messagebus.rabbitmq.admin import RMQAdmin, must_get_rmq_admin


class RMQConsumer(Consumer):
    def __init__(
        self,
        logger: logging.Logger,
        connection_string: str,
        serializer: Optional[MessageSerializer] = None,
        rmq_admin: Optional[RMQAdmin] = None,
        retry: int = 5,
        retry_interval: int = 10,
        prefetch_count: int = 20,
        identifier="rmq-consumer",
    ):
        self.logger = logger
        self.rmq_admin = must_get_rmq_admin(
            logger=logger, rmq_admin=rmq_admin, connection_string=connection_string
        )
        self.connection_string = connection_string
        self.connection: Optional[aiormq.Connection] = None
        self.channel: Optional[aiormq.Channel] = None
        self.serializer = must_get_message_serializer(serializer)
        self.retry = retry
        self.retry_interval = retry_interval
        self.prefetch_count = prefetch_count
        self._handlers: Mapping[str, TEventHandler] = {}
        self._is_start_triggered = False
        self._is_stop_triggered = False
        self.identifier = identifier

    def register(self, event_name: str) -> Callable[[TEventHandler], Any]:
        def wrapper(handler: TEventHandler):
            self.logger.warning(
                f'🐰 [{self.identifier}] Register handler for "{event_name}"'
            )
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
            await self._connect()
            event_names = list(self._handlers.keys())
            await self.rmq_admin.create_events(event_names)
            f'🐰 [{self.identifier}] Listening from "{event_names}"'
            for event_name in event_names:
                queue_name = self.rmq_admin.get_queue_name(event_name)
                on_message = self._create_consumer_callback(self.channel, event_name)
                await self.channel.basic_consume(
                    queue=queue_name, consumer_callback=on_message
                )
            retry = self.retry
            while not self._is_stop_triggered:
                await asyncio.sleep(0.01)
                if not self._is_stop_triggered and (
                    self.connection is None or self.connection.is_closed
                ):
                    raise Exception("Rabbitmq connection is closed")
        except (asyncio.CancelledError, GeneratorExit, Exception) as e:
            if retry > 0:
                self.logger.error(f"🐰 [{self.identifier}]", exc_info=True)
            if retry == 0:
                self.logger.error(
                    f"🐰 [{self.identifier}] Failed to consume message after "
                    + f"{self.retry} attempts"
                )
                raise e
            await self._disconnect()
            await asyncio.sleep(self.retry_interval)
            await self._start(retry - 1)
        finally:
            await self._disconnect()

    async def _connect(self):
        try:
            connection_created = False
            if self.connection is None or self.connection.is_closed:
                self.logger.info(f"🐰 [{self.identifier}] Create consumer connection")
                self.connection = await aiormq.connect(self.connection_string)
                self.logger.info(f"🐰 [{self.identifier}] Consumer connection created")
                connection_created = True
            if connection_created or self.channel is None or self.channel.is_closed:
                self.logger.info(f"🐰 [{self.identifier}] Get consumer channel")
                self.channel = await self.connection.channel()
                await self.channel.basic_qos(prefetch_count=self.prefetch_count)
                self.logger.info(f"🐰 [{self.identifier}] Consumer channel created")
        except (asyncio.CancelledError, GeneratorExit, Exception):
            self.logger.error(f"🐰 [{self.identifier}]", exc_info=True)
            raise Exception("Cannot connect")

    async def _disconnect(self):
        try:
            if self.channel is not None and not self.channel.is_closed:
                self.logger.info(f"🐰 [{self.identifier}] Close consumer channel")
                await self.channel.close()
                self.logger.info(f"🐰 [{self.identifier}] Consumer channel closed")
        except (asyncio.CancelledError, GeneratorExit, Exception):
            self.logger.error(f"🐰 [{self.identifier}]", exc_info=True)
        try:
            if self.connection is not None and not self.connection.is_closed:
                self.logger.info(f"🐰 [{self.identifier}] Close consumer connection")
                await self.connection.close()
                self.logger.info(f"🐰 [{self.identifier}] Consumer connection closed")
        except (asyncio.CancelledError, GeneratorExit, Exception):
            self.logger.error(f"🐰 [{self.identifier}]", exc_info=True)
        self.connection = None
        self.channel = None

    def _create_consumer_callback(
        self,
        channel: aiormq.Channel,
        event_name: str,
    ) -> Callable[[Any], Any]:
        async def on_message(message):
            try:
                decoded_value = self.serializer.decode(event_name, message.body)
                handler = self._handlers.get(event_name)
                queue_name = self.rmq_admin.get_queue_name(event_name)
                self.logger.info(
                    f'🐰 [{self.identifier}] Consume from "{queue_name}": '
                    + f"{decoded_value}"
                )
                await self._run_handler(handler, decoded_value)
                await channel.basic_ack(message.delivery_tag)
            except (asyncio.CancelledError, GeneratorExit, Exception):
                self.logger.error(f"🐰 [{self.identifier}]", exc_info=True)

        return on_message

    async def _run_handler(self, message_handler: TEventHandler, decoded_value: Any):
        if inspect.iscoroutinefunction(message_handler):
            return asyncio.create_task(message_handler(decoded_value))
        return message_handler(decoded_value)
