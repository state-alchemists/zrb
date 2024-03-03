import asyncio
import logging
from typing import Any, List, Mapping, Optional

import aiormq
from component.messagebus.messagebus import Admin


class RMQEventConfig:
    def __init__(
        self,
        queue_name: str,
        exchange_name: str = "",
    ):
        self.queue_name = queue_name
        self.exchange_name = exchange_name


class RMQAdmin(Admin):
    def __init__(
        self,
        logger: logging.Logger,
        configs: Mapping[str, RMQEventConfig],
        connection_string: str,
    ):
        self.logger = logger
        self.connection_string = connection_string
        self.configs = configs
        self._existing_events: Mapping[str, bool] = {}

    async def create_events(self, event_names: List[str]):
        # Only handle non-existing events
        event_names = [
            event_name
            for event_name in event_names
            if event_name not in self._existing_events
        ]
        if len(event_names) == 0:
            return
        try:
            connection = await aiormq.connect(self.connection_string)
            channel = await connection.channel()
            for event_name in event_names:
                config = self.get_config(event_name)
                if config.exchange_name != "":
                    await self._declare_fanned_out_exchange(channel, config)
                    self._existing_events[event_name] = True
                    continue
                await self._declare_queue(channel, config)
                self._existing_events[event_name] = True
            await self._clean_up(connection, channel)
        except (asyncio.CancelledError, GeneratorExit, Exception):
            self.logger.error(
                " ".join(
                    [
                        "🐰 [rabbitmq-admin] Something wrong when ",
                        f"creating events: {event_names}",
                    ]
                ),
                exc_info=True,
            )

    async def delete_events(self, event_names: List[str]):
        # Only handle existing events
        event_names = [
            event_name
            for event_name in event_names
            if event_name in self._existing_events
        ]
        if len(event_names) == 0:
            return
        try:
            connection = await aiormq.connect(self.connection_string)
            channel = await connection.channel()
            for event_name in event_names:
                config = self.get_config(event_name)
                # delete the queue
                await channel.queue_delete(queue=config.queue_name)
                if config.exchange_name != "":
                    # delete the exchange
                    await channel.exchange_delete(exchange_name=config.exchange_name)
                del self._existing_events[event_name]
            await self._clean_up(connection, channel)
        except (asyncio.CancelledError, GeneratorExit, Exception):
            self.logger.error(
                " ".join(
                    [
                        "🐰 [rabbitmq-admin] Something wrong when ",
                        f"deleting events: {event_names}",
                    ]
                ),
                exc_info=True,
            )

    async def _clean_up(self, connection: aiormq.Connection, channel: aiormq.Channel):
        try:
            await channel.close()
            await connection.close()
        except (asyncio.CancelledError, GeneratorExit, Exception):
            self.logger.error("🐰 [rabbitmq-admin]", exc_info=True)

    async def _declare_fanned_out_exchange(
        self, channel: aiormq.Channel, config: RMQEventConfig
    ):
        await channel.exchange_declare(
            exchange=config.exchange_name,
            exchange_type="fanout",
            durable=False,
            auto_delete=False,
        )
        # declare a queue
        result = await self._declare_queue(channel, config)
        queue_name = result["queue"]
        # bind the queue to the exchange
        await channel.queue_bind(
            queue=queue_name, exchange=config.exchange_name, routing_key=""
        )

    async def _declare_queue(
        self, channel: aiormq.Channel, config: RMQEventConfig
    ) -> Any:
        return await channel.queue_declare(
            queue=config.queue_name, durable=True, auto_delete=False
        )

    def get_config(self, event_name: str) -> RMQEventConfig:
        if event_name in self.configs:
            return self.configs[event_name]
        return RMQEventConfig(queue_name=event_name)

    def get_exchange_name(self, event_name: str) -> str:
        event_config = self.get_config(event_name)
        return event_config.exchange_name

    def get_queue_name(self, event_name: str) -> str:
        event_config = self.get_config(event_name)
        return event_config.queue_name


def must_get_rmq_admin(
    logger: logging.Logger, rmq_admin: Optional[RMQAdmin], connection_string: str
) -> RMQAdmin:
    if rmq_admin is None:
        return RMQAdmin(logger=logger, configs={}, connection_string=connection_string)
    return rmq_admin
