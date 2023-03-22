from typing import Any, Optional
from core.messagebus.messagebus import (
    Publisher,  MessageSerializer, get_message_serializer
)
import aiormq
import logging


class RMQPublishConnection():
    def __init__(self, logger: logging.Logger, connection_string: str):
        self.logger = logger
        self.connection_string = connection_string
        self.connection: Optional[aiormq.Connection] = None

    async def __aenter__(self):
        self.logger.info('🐰 Create publisher connection')
        self.connection = await aiormq.connect(self.connection_string)
        self.logger.info('🐰 Publisher connection created')
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.logger.info('🐰 Close publisher connection')
        await self.connection.close()
        self.logger.info('🐰 Publisher connection closed')


class RMQPublisher(Publisher):
    def __init__(
        self,
        logger: logging.Logger,
        publish_connection: RMQPublishConnection,
        serializer: Optional[MessageSerializer] = None,
        retry: int = 5
    ):
        self.logger = logger
        self.serializer = get_message_serializer(serializer)
        self.conn = publish_connection
        self._retry = retry

    async def publish(self, event_name: str, message: Any):
        return await self._publish(event_name, message, self._retry)

    async def _publish(self, event_name: str, message: Any, retry: int):
        try:
            async with self.conn as conn:
                connection: aiormq.Connection = conn.connection
                self.logger.info('🐰 Get channel')
                channel = await connection.channel()
                self.logger.info(f'🐰 Declare queue: {event_name}')
                await channel.queue_declare(event_name)
                self.logger.info(f'🐰 Publish "{event_name}": {message}')
                await channel.basic_publish(
                    body=self.serializer.encode(event_name, message),
                    routing_key=event_name,
                )
            retry = self._retry
        except Exception:
            if retry == 0:
                raise
            await self._publish(event_name, message, retry-1)

