import asyncio
import logging
from typing import Any, Optional

from aiokafka import AIOKafkaProducer
from aiokafka.producer.producer import DefaultPartitioner, _missing
from component.messagebus.kafka.admin import KafkaAdmin, must_get_kafka_admin
from component.messagebus.messagebus import (
    MessageSerializer,
    Publisher,
    must_get_message_serializer,
)
from pydantic import BaseModel


class KafkaPublisher(Publisher):
    def __init__(
        self,
        logger: logging.Logger,
        bootstrap_servers: str = "localhost",
        client_id: Optional[Any] = None,
        metadata_max_age_ms=300000,
        request_timeout_ms=40000,
        api_version="auto",
        acks=_missing,
        key_serializer=None,
        value_serializer=None,
        compression_type=None,
        max_batch_size=16384,
        partitioner=DefaultPartitioner(),
        max_request_size=1048576,
        linger_ms=0,
        send_backoff_ms=100,
        retry_backoff_ms=100,
        security_protocol="PLAINTEXT",
        ssl_context=None,
        connections_max_idle_ms=540000,
        enable_idempotence=False,
        transactional_id=None,
        transaction_timeout_ms=60000,
        sasl_mechanism="PLAIN",
        sasl_plain_password=None,
        sasl_plain_username=None,
        sasl_kerberos_service_name="kafka",
        sasl_kerberos_domain_name=None,
        sasl_oauth_token_provider=None,
        serializer: Optional[MessageSerializer] = None,
        kafka_admin: Optional[KafkaAdmin] = None,
        retry: int = 3,
        retry_interval: int = 10,
        identifier="kafka-publisher",
    ):
        self.logger = logger
        self.serializer = must_get_message_serializer(serializer)
        self.kafka_admin = must_get_kafka_admin(
            logger=logger,
            kafka_admin=kafka_admin,
            bootstrap_servers=bootstrap_servers,
            security_protocol=security_protocol,
            sasl_mechanism=sasl_mechanism,
            sasl_plain_password=sasl_plain_password,
            sasl_plain_username=sasl_plain_username,
            sasl_kerberos_service_name=sasl_kerberos_service_name,
            sasl_kerberos_domain_name=sasl_kerberos_domain_name,
            sasl_oauth_token_provider=sasl_oauth_token_provider,
        )
        self.producer: Optional[AIOKafkaProducer] = None
        self.bootstrap_servers = bootstrap_servers
        self.client_id = client_id
        self.metadata_max_age_ms = metadata_max_age_ms
        self.request_timeout_ms = request_timeout_ms
        self.api_version = api_version
        self.acks = acks
        self.key_serializer = key_serializer
        self.value_serializer = value_serializer
        self.compression_type = compression_type
        self.max_batch_size = max_batch_size
        self.partitioner = partitioner
        self.max_request_size = max_request_size
        self.linger_ms = linger_ms
        self.send_backoff_ms = send_backoff_ms
        self.retry_backoff_ms = retry_backoff_ms
        self.security_protocol = security_protocol
        self.ssl_context = ssl_context
        self.connections_max_idle_ms = connections_max_idle_ms
        self.enable_idempotence = enable_idempotence
        self.transactional_id = transactional_id
        self.transaction_timeout_ms = transaction_timeout_ms
        self.sasl_mechanism = sasl_mechanism
        self.sasl_plain_password = sasl_plain_password
        self.sasl_plain_username = sasl_plain_username
        self.sasl_kerberos_service_name = sasl_kerberos_service_name
        self.sasl_kerberos_domain_name = sasl_kerberos_domain_name
        self.sasl_oauth_token_provider = sasl_oauth_token_provider
        self.retry = retry
        self.retry_interval = retry_interval
        self.identifier = identifier

    async def publish(self, event_name: str, message: Any):
        await self.kafka_admin.create_events([event_name])
        topic_name = self.kafka_admin.get_topic_name(event_name)
        if isinstance(message, BaseModel):
            message = message.model_dump()
        for attempt in range(self.retry):
            try:
                await self._connect()
                encoded_value = self.serializer.encode(event_name, message)
                self.logger.info(
                    f'🐼 [{self.identifier}] Publish to "{topic_name}": ' + f"{message}"
                )
                return await self.producer.send_and_wait(topic_name, encoded_value)
            except (asyncio.CancelledError, GeneratorExit, Exception) as e:
                self.logger.error(
                    f"🐼 [{self.identifier}] Failed to publish message: {e}"
                )
                await self._disconnect()
                await asyncio.sleep(self.retry_interval)
                continue
        self.logger.error(
            f"🐼 [{self.identifier}] Failed to publish message after "
            + f"{self.retry} attempts"
        )
        raise RuntimeError("Failed to publish message after retrying")

    async def _connect(self):
        self.logger.info(f"🐼 [{self.identifier}] Create kafka producer")
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            client_id=self.client_id,
            metadata_max_age_ms=self.metadata_max_age_ms,
            request_timeout_ms=self.request_timeout_ms,
            api_version=self.api_version,
            acks=self.acks,
            key_serializer=self.key_serializer,
            value_serializer=self.value_serializer,
            compression_type=self.compression_type,
            max_batch_size=self.max_batch_size,
            partitioner=self.partitioner,
            max_request_size=self.max_request_size,
            linger_ms=self.linger_ms,
            send_backoff_ms=self.send_backoff_ms,
            retry_backoff_ms=self.retry_backoff_ms,
            security_protocol=self.security_protocol,
            ssl_context=self.ssl_context,
            connections_max_idle_ms=self.connections_max_idle_ms,
            enable_idempotence=self.enable_idempotence,
            transactional_id=self.transactional_id,
            transaction_timeout_ms=self.transaction_timeout_ms,
            sasl_mechanism=self.sasl_mechanism,
            sasl_plain_password=self.sasl_plain_password,
            sasl_plain_username=self.sasl_plain_username,
            sasl_kerberos_service_name=self.sasl_kerberos_service_name,
            sasl_kerberos_domain_name=self.sasl_kerberos_domain_name,
            sasl_oauth_token_provider=self.sasl_oauth_token_provider,
        )
        self.logger.info(f"🐼 [{self.identifier}] Start kafka producer")
        await self.producer.start()
        self.logger.info(f"🐼 [{self.identifier}] Kafka producer started")
        return self

    async def _disconnect(self):
        self.logger.info(f"🐼 [{self.identifier}] Stop kafka producer")
        if self.producer is not None:
            await self.producer.stop()
        self.logger.info(f"🐼 [{self.identifier}] Kafka producer stopped")
        self.producer = None
