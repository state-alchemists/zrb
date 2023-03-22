from typing import Any, Callable, Mapping, Optional
from core.messagebus.messagebus import (
    Consumer, THandler, MessageSerializer,
    get_message_serializer
)
from aiokafka import AIOKafkaConsumer, __version__
from aiokafka.consumer.consumer import RoundRobinPartitionAssignor

import asyncio
import inspect
import logging


class KafkaConsumeConnection():
    def __init__(
        self,
        logger: logging.Logger,
        bootstrap_servers: str,
        client_id='aiokafka-' + __version__,
        group_id: Optional[str] = None,
        key_deserializer=None,
        value_deserializer=None,
        fetch_max_wait_ms=500,
        fetch_max_bytes=52428800,
        fetch_min_bytes=1,
        max_partition_fetch_bytes=1 * 1024 * 1024,
        request_timeout_ms=40 * 1000,
        retry_backoff_ms=100,
        auto_offset_reset='latest',
        enable_auto_commit=True,
        auto_commit_interval_ms=5000,
        check_crcs=True,
        metadata_max_age_ms=5 * 60 * 1000,
        partition_assignment_strategy=(RoundRobinPartitionAssignor,),
        max_poll_interval_ms=300000,
        rebalance_timeout_ms=None,
        session_timeout_ms=10000,
        heartbeat_interval_ms=3000,
        consumer_timeout_ms=200,
        max_poll_records=None,
        ssl_context=None,
        security_protocol='PLAINTEXT',
        api_version='auto',
        exclude_internal_topics=True,
        connections_max_idle_ms=540000,
        isolation_level="read_uncommitted",
        sasl_mechanism="PLAIN",
        sasl_plain_password=None,
        sasl_plain_username=None,
        sasl_kerberos_service_name='kafka',
        sasl_kerberos_domain_name=None,
        sasl_oauth_token_provider=None
    ):
        self.logger = logger
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.bootstrap_servers = bootstrap_servers
        self.client_id = client_id
        self.group_id = group_id
        self.key_deserializer = key_deserializer
        self.value_deserializer = value_deserializer
        self.fetch_max_wait_ms = fetch_max_wait_ms
        self.fetch_max_bytes = fetch_max_bytes
        self.fetch_min_bytes = fetch_min_bytes
        self.max_partition_fetch_bytes = max_partition_fetch_bytes
        self.request_timeout_ms = request_timeout_ms
        self.retry_backoff_ms = retry_backoff_ms
        self.auto_offset_reset = auto_offset_reset
        self.enable_auto_commit = enable_auto_commit
        self.auto_commit_interval_ms = auto_commit_interval_ms
        self.check_crcs = check_crcs
        self.metadata_max_age_ms = metadata_max_age_ms
        self.partition_assignment_strategy = partition_assignment_strategy
        self.max_poll_interval_ms = max_poll_interval_ms
        self.rebalance_timeout_ms = rebalance_timeout_ms
        self.session_timeout_ms = session_timeout_ms
        self.heartbeat_interval_ms = heartbeat_interval_ms
        self.consumer_timeout_ms = consumer_timeout_ms
        self.max_poll_records = max_poll_records
        self.ssl_context = ssl_context
        self.security_protocol = security_protocol
        self.api_version = api_version
        self.exclude_internal_topics = exclude_internal_topics
        self.connections_max_idle_ms = connections_max_idle_ms
        self.isolation_level = isolation_level
        self.sasl_mechanism = sasl_mechanism
        self.sasl_plain_password = sasl_plain_password
        self.sasl_plain_username = sasl_plain_username
        self.sasl_kerberos_service_name = sasl_kerberos_service_name
        self.sasl_kerberos_domain_name = sasl_kerberos_domain_name
        self.sasl_oauth_token_provider = sasl_oauth_token_provider

    async def __aenter__(self):
        self.logger.info('🐼 Create kafka consumer')
        self.consumer = AIOKafkaConsumer(
            bootstrap_servers=self.bootstrap_servers,
            client_id=self.client_id,
            group_id=self.group_id,
            key_deserializer=self.key_deserializer,
            value_deserializer=self.value_deserializer,
            fetch_max_wait_ms=self.fetch_max_wait_ms,
            fetch_max_bytes=self.fetch_max_bytes,
            fetch_min_bytes=self.fetch_min_bytes,
            max_partition_fetch_bytes=self.max_partition_fetch_bytes,
            request_timeout_ms=self.request_timeout_ms,
            retry_backoff_ms=self.retry_backoff_ms,
            auto_offset_reset=self.auto_offset_reset,
            enable_auto_commit=self.enable_auto_commit,
            auto_commit_interval_ms=self.auto_commit_interval_ms,
            check_crcs=self.check_crcs,
            metadata_max_age_ms=self.metadata_max_age_ms,
            partition_assignment_strategy=self.partition_assignment_strategy,
            max_poll_interval_ms=self.max_poll_interval_ms,
            rebalance_timeout_ms=self.rebalance_timeout_ms,
            session_timeout_ms=self.session_timeout_ms,
            heartbeat_interval_ms=self.heartbeat_interval_ms,
            consumer_timeout_ms=self.consumer_timeout_ms,
            max_poll_records=self.max_poll_records,
            ssl_context=self.ssl_context,
            security_protocol=self.security_protocol,
            api_version=self.api_version,
            exclude_internal_topics=self.exclude_internal_topics,
            connections_max_idle_ms=self.connections_max_idle_ms,
            isolation_level=self.isolation_level,
            sasl_mechanism=self.sasl_mechanism,
            sasl_plain_password=self.sasl_plain_password,
            sasl_plain_username=self.sasl_plain_username,
            sasl_kerberos_service_name=self.sasl_kerberos_service_name,
            sasl_kerberos_domain_name=self.sasl_kerberos_domain_name,
            sasl_oauth_token_provider=self.sasl_oauth_token_provider,
        )
        self.logger.info('🐼 Start kafka consumer')
        await self.consumer.start()
        self.logger.info('🐼 Kafka consumer started')
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.logger.info('🐼 Unsubscribe kafka consumer from all topics')
        self.consumer.unsubscribe()
        self.logger.info('🐼 Stop kafka consumer')
        await self.consumer.stop()
        self.logger.info('🐼 Kafka consumer stopped')


class KafkaConsumer(Consumer):
    def __init__(
        self,
        logger: logging.Logger,
        consume_connection: KafkaConsumeConnection,
        serializer: Optional[MessageSerializer] = None,
        retry: int = 5
    ):
        self.logger = logger
        self.serializer = get_message_serializer(serializer)
        self.conn = consume_connection
        self._handlers: Mapping[str, THandler] = {}
        self._retry = retry

    def register(self, event_name: str) -> Callable[[THandler], Any]:
        def wrapper(handler: THandler):
            self.logger.warning(f'🐼 Register handler for "{event_name}"')
            self._handlers[event_name] = handler
            return handler
        return wrapper

    async def run(self):
        return await self._run(self._retry)

    async def _run(self, retry: int):
        try:
            async with self.conn as conn:
                consumer: AIOKafkaConsumer = conn.consumer
                topics = list(self._handlers.keys())
                self.logger.warning(f'🐼 Subscribe to topics: {topics}')
                consumer.subscribe(topics=topics)
                async for message in consumer:
                    event_name = message.topic
                    message_handler = self._handlers.get(event_name)
                    decoded_value = self.serializer.decode(
                        event_name, message.value
                    )
                    self.logger.info(
                        f'🐼 Consume "{event_name}": {decoded_value}'
                    )
                    await self._run_handler(message_handler, decoded_value)
                retry = self._retry
        except Exception:
            if retry == 0:
                self.logger.fatal('🐼 Cannot retry')
                raise
            self.logger.warning('🐼 Retry to consume')
            await self._run(retry-1)

    async def _run_handler(
        self, message_handler: THandler, decoded_value: Any
    ):
        if inspect.iscoroutinefunction(message_handler):
            return asyncio.create_task(message_handler(decoded_value))
        return message_handler(decoded_value)
