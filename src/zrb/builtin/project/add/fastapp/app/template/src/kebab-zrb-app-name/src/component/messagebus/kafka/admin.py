import asyncio
import logging
from typing import List, Mapping, Optional

from aiokafka import __version__
from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from component.messagebus.messagebus import Admin


class KafkaEventConfig:
    def __init__(
        self, topic_name: str, num_partitions: int = 1, replication_factor: int = 1
    ):
        self.topic_name = topic_name
        self.num_partitions = num_partitions
        self.replication_factor = replication_factor


class KafkaAdmin(Admin):
    def __init__(
        self,
        logger: logging.Logger,
        bootstrap_servers: str,
        configs: Mapping[str, KafkaEventConfig],
        client_id: str = "kafka-admin-" + __version__,
        security_protocol="PLAINTEXT",
        sasl_mechanism="PLAIN",
        sasl_plain_password=None,
        sasl_plain_username=None,
        sasl_kerberos_service_name="kafka",
        sasl_kerberos_domain_name=None,
        sasl_oauth_token_provider=None,
    ):
        self.logger = logger
        self.configs = configs
        self.bootstrap_servers = bootstrap_servers
        self.client_id = client_id
        self.security_protocol = security_protocol
        self.sasl_mechanism = sasl_mechanism
        self.sasl_plain_password = sasl_plain_password
        self.sasl_plain_username = sasl_plain_username
        self.sasl_kerberos_service_name = sasl_kerberos_service_name
        self.sasl_kerberos_domain_name = sasl_kerberos_domain_name
        self.sasl_oauth_token_provider = sasl_oauth_token_provider
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
        # Create topics
        topics = [self.get_new_topic(event_name) for event_name in event_names]
        try:
            admin_client = self._create_connection()
            admin_client.create_topics(topics)
            admin_client.close()
        except (asyncio.CancelledError, GeneratorExit, Exception):
            self.logger.error(
                " ".join(
                    [
                        "🐼 [kafka-admin] Something wrong when ",
                        f"creating topics: {topics}",
                    ]
                ),
                exc_info=True,
            )
        for event_name in event_names:
            self._existing_events[event_name] = True

    async def delete_events(self, event_names: List[str]):
        # Only handle existing events
        event_names = [
            event_name
            for event_name in event_names
            if event_name in self._existing_events
        ]
        if len(event_names) == 0:
            return
        # Create topic names
        topic_names = [
            self.get_topic_name(event_name)
            for event_name in event_names
            if event_name in self._existing_events
        ]
        try:
            admin_client = self._create_connection()
            admin_client.delete_topics(topic_names)
            admin_client.close()
            for event_name in event_names:
                del self._existing_events[event_name]
        except (asyncio.CancelledError, GeneratorExit, Exception):
            self.logger.error(
                " ".join(
                    [
                        "🐼 [kafka-admin] Something wrong when ",
                        f"deleting topics: {topic_names}",
                    ]
                ),
                exc_info=True,
            )

    def get_config(self, event_name: str) -> KafkaEventConfig:
        if event_name in self.configs:
            return self.configs[event_name]
        return KafkaEventConfig(topic_name=event_name)

    def get_topic_name(self, event_name: str) -> str:
        event_config = self.get_config(event_name)
        return event_config.topic_name

    def get_new_topic(self, event_name: str) -> NewTopic:
        event_config = self.get_config(event_name)
        topic = NewTopic(
            name=event_config.topic_name,
            num_partitions=event_config.num_partitions,
            replication_factor=event_config.replication_factor,
        )
        return topic

    def _create_connection(self) -> AIOKafkaAdminClient:
        return AIOKafkaAdminClient(
            bootstrap_servers=self.bootstrap_servers,
            client_id=self.client_id,
            security_protocol=self.security_protocol,
            sasl_mechanism=self.sasl_mechanism,
            sasl_plain_password=self.sasl_plain_password,
            sasl_plain_username=self.sasl_plain_username,
            sasl_kerberos_service_name=self.sasl_kerberos_service_name,
            sasl_kerberos_domain_name=self.sasl_kerberos_domain_name,
            sasl_oauth_token_provider=self.sasl_oauth_token_provider,
        )


def must_get_kafka_admin(
    logger: logging.Logger,
    kafka_admin: Optional[KafkaAdmin],
    bootstrap_servers: str,
    client_id="kafka-admin-" + __version__,
    security_protocol="PLAINTEXT",
    sasl_mechanism="PLAIN",
    sasl_plain_password=None,
    sasl_plain_username=None,
    sasl_kerberos_service_name="kafka",
    sasl_kerberos_domain_name=None,
    sasl_oauth_token_provider=None,
) -> KafkaAdmin:
    if kafka_admin is None:
        return KafkaAdmin(
            logger=logger,
            bootstrap_servers=bootstrap_servers,
            configs={},
            client_id=client_id,
            security_protocol=security_protocol,
            sasl_mechanism=sasl_mechanism,
            sasl_plain_password=sasl_plain_password,
            sasl_plain_username=sasl_plain_username,
            sasl_kerberos_service_name=sasl_kerberos_service_name,
            sasl_kerberos_domain_name=sasl_kerberos_domain_name,
            sasl_oauth_token_provider=sasl_oauth_token_provider,
        )
    return kafka_admin
