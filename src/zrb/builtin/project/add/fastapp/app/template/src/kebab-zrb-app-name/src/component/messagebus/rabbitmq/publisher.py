import asyncio
import logging
from typing import Any, Optional

import aiormq
from component.messagebus.messagebus import (
    MessageSerializer,
    Publisher,
    must_get_message_serializer,
)
from component.messagebus.rabbitmq.admin import RMQAdmin, must_get_rmq_admin
from pydantic import BaseModel


class RMQPublisher(Publisher):
    def __init__(
        self,
        logger: logging.Logger,
        connection_string: str,
        serializer: Optional[MessageSerializer] = None,
        rmq_admin: Optional[RMQAdmin] = None,
        retry: int = 5,
        retry_interval: int = 10,
        identifier="rmq-publisher",
    ):
        self.logger = logger
        self.rmq_admin = must_get_rmq_admin(
            logger=logger, rmq_admin=rmq_admin, connection_string=connection_string
        )
        self.connection_string = connection_string
        self.connection: Optional[aiormq.Connection] = None
        self.serializer = must_get_message_serializer(serializer)
        self.retry = retry
        self.retry_interval = retry_interval
        self.identifier = identifier

    async def publish(self, event_name: str, message: Any):
        await self.rmq_admin.create_events([event_name])
        queue_name = self.rmq_admin.get_queue_name(event_name)
        exchange_name = self.rmq_admin.get_exchange_name(event_name)
        if isinstance(message, BaseModel):
            message = message.model_dump()
        for attempt in range(self.retry):
            try:
                await self._connect()
                self.logger.info(f"🐰 [{self.identifier}] Get channel")
                self.logger.info(
                    f'🐰 [{self.identifier}] Publish to "{queue_name}": ' + f"{message}"
                )
                await self.channel.basic_publish(
                    body=self.serializer.encode(event_name, message),
                    exchange=exchange_name,
                    routing_key=queue_name if exchange_name == "" else "",
                )
                return
            except (asyncio.CancelledError, GeneratorExit, Exception) as e:
                self.logger.error(
                    f"🐰 [{self.identifier}] Failed to publish message: {e}"
                )
                await self._disconnect()
                await asyncio.sleep(self.retry_interval)
                continue
        self.logger.error(
            f"🐰 [{self.identifier}] Failed to publish message after "
            + f"{self.retry} attempts"
        )
        raise RuntimeError("Failed to publish message after retrying")

    async def _connect(self):
        try:
            connection_created = False
            if self.connection is None or self.connection.is_closed:
                self.logger.info(f"🐰 [{self.identifier}] Create publisher connection")
                self.connection = await aiormq.connect(self.connection_string)
                self.logger.info(f"🐰 [{self.identifier}] Publisher connection created")
                connection_created = True
            if connection_created or self.channel is None or self.channel.is_closed:
                self.logger.info(f"🐰 [{self.identifier}] Get publisher channel")
                self.channel = await self.connection.channel()
                self.logger.info(f"🐰 [{self.identifier}] publisher channel created")
        except (asyncio.CancelledError, GeneratorExit, Exception):
            self.logger.error(f"🐰 [{self.identifier}]", exc_info=True)
            raise Exception("Cannot connect")

    async def _disconnect(self):
        try:
            if self.channel is not None and not self.channel.is_closed:
                self.logger.info(f"🐰 [{self.identifier}] Close publisher channel")
                await self.channel.close()
                self.logger.info(f"🐰 [{self.identifier}] Publisher channel closed")
        except (asyncio.CancelledError, GeneratorExit, Exception):
            self.logger.error(f"🐰 [{self.identifier}]", exc_info=True)
        try:
            if self.connection is not None and not self.connection.is_closed:
                self.logger.info(f"🐰 [{self.identifier}] Close publisher connection")
                await self.connection.close()
                self.logger.info(f"🐰 [{self.identifier}] Publisher connection closed")
        except (asyncio.CancelledError, GeneratorExit, Exception):
            self.logger.error(f"🐰 [{self.identifier}]", exc_info=True)
        self.connection = None
        self.channel = None
