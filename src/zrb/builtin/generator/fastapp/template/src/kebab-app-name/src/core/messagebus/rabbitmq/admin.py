from typing import Any, Mapping, List, Optional
from core.messagebus.messagebus import Admin
import logging
import aiormq


class RMQEventConfig():
    def __init__(
        self,
        queue_name: str,
        exchange_name: str = '',
    ):
        self.queue_name = queue_name
        self.exchange_name = exchange_name


class RMQAdmin(Admin):
    def __init__(
        self,
        logger: logging.Logger,
        configs: Mapping[str, RMQEventConfig],
        connection_string: str
    ):
        self.logger = logger
        self.connection_string = connection_string
        self.configs = configs

    async def create_events(self, event_names: List[str]):
        connection = await aiormq.connect(self.connection_string)
        channel = await connection.channel()
        for event_name in event_names:
            config = self.get_config(event_name)
            if config.exchange_name != '':
                await self._declare_fanned_out_exchange(channel, config)
                continue
            await self._declare_queue(channel, config)
        channel.close()
        connection.close()

    async def delete_events(self, event_names: List[str]):
        connection = await aiormq.connect(self.connection_string)
        channel = await connection.channel()
        for event_name in event_names:
            config = self.get_config(event_name)
            # delete the queue
            await channel.queue_delete(queue_name=config.queue_name)
            if config.exchange_name != '':
                # delete the exchange
                await channel.exchange_delete(
                    exchange_name=config.exchange_name
                )
        channel.close()
        connection.close()

    async def _declare_fanned_out_exchange(
        self, channel: aiormq.Channel, config: RMQEventConfig
    ):
        await channel.exchange_declare(
            exchange=config.exchange_name,
            exchange_type='fanout',
            durable=False,
            auto_delete=False
        )
        # declare a queue
        result = await self._declare_queue(channel, config)
        queue_name = result['queue']
        # bind the queue to the exchange
        await channel.queue_bind(
            queue=queue_name,
            exchange=config.exchange_name,
            routing_key=''
        )

    async def _declare_queue(
        self, channel: aiormq.Channel, config: RMQEventConfig
    ) -> Any:
        return await channel.queue_declare(
            queue=config.queue_name,
            durable=False,
            auto_delete=False
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
    logger: logging.Logger,
    rmq_admin: Optional[RMQAdmin],
    connection_string: str
) -> RMQAdmin:
    if rmq_admin is None:
        return RMQAdmin(
            logger=logger,
            configs={},
            connection_string=connection_string
        )
    return rmq_admin
