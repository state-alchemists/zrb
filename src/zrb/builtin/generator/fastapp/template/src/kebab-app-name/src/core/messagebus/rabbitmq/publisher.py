from typing import Any, Optional
from core.messagebus.messagebus import (
    Publisher,  MessageSerializer, must_get_message_serializer
)
from core.messagebus.rabbitmq.admin import (
    RMQAdmin, must_get_rmq_admin
)
import aiormq
import asyncio
import logging


class RMQPublisher(Publisher):
    def __init__(
        self,
        logger: logging.Logger,
        connection_string: str,
        serializer: Optional[MessageSerializer] = None,
        rmq_admin: Optional[RMQAdmin] = None,
        retry: int = 3,
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

    async def publish(self, event_name: str, message: Any):
        await self.rmq_admin.create_events([event_name])
        queue_name = self.rmq_admin.get_queue_name(event_name)
        exchange_name = self.rmq_admin.get_exchange_name(event_name)
        for attempt in range(self.retry):
            try:
                if self.connection is None or self.connection.is_closed:
                    await self._connect()
                self.logger.info('🐰 Get channel')
                channel = await self.connection.channel()
                self.logger.info(f'🐰 Publish to "{queue_name}": {message}')
                await channel.basic_publish(
                    body=self.serializer.encode(event_name, message),
                    exchange=exchange_name,
                    routing_key=queue_name if exchange_name == '' else '',
                )
                return
            except Exception as e:
                self.logger.error(f'🐰 Failed to publish message: {e}')
                await self._disconnect()
                await asyncio.sleep(self.retry_interval)
                continue
        self.logger.error(
            f'🐰 Failed to publish message after {self.retry} attempts'
        )
        raise RuntimeError('Failed to publish message after retrying')

    async def _connect(self):
        self.logger.info('🐰 Create publisher connection')
        self.connection = await aiormq.connect(self.connection_string)
        self.logger.info('🐰 Publisher connection created')

    async def _disconnect(self):
        self.logger.info('🐰 Close publisher connection')
        if self.connection is not None:
            await self.connection.close()
        self.logger.info('🐰 Publisher connection closed')
        self.connection = None
