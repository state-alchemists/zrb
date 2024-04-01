import asyncio
import inspect
import logging
from typing import Any, Callable, Mapping, Optional

from aiokafka import AIOKafkaConsumer, __version__
from aiokafka.consumer.consumer import RoundRobinPartitionAssignor
from component.messagebus.kafka.admin import KafkaAdmin, must_get_kafka_admin
from component.messagebus.messagebus import (
    Consumer,
    MessageSerializer,
    TEventHandler,
    must_get_message_serializer,
)


class KafkaConsumer(Consumer):
    def __init__(
        self,
        logger: logging.Logger,
        bootstrap_servers: str,
        client_id="aiokafka-" + __version__,
        group_id: Optional[str] = None,
        key_deserializer=None,
        value_deserializer=None,
        fetch_max_wait_ms=500,
        fetch_max_bytes=52428800,
        fetch_min_bytes=1,
        max_partition_fetch_bytes=1 * 1024 * 1024,
        request_timeout_ms=40 * 1000,
        retry_backoff_ms=100,
        auto_offset_reset="latest",
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
        security_protocol="PLAINTEXT",
        api_version="auto",
        exclude_internal_topics=True,
        connections_max_idle_ms=540000,
        isolation_level="read_uncommitted",
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
        identifier="kafka-consumer",
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
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.retry = retry
        self.retry_interval = retry_interval
        self._handlers: Mapping[str, TEventHandler] = {}
        self._is_start_triggered = False
        self._is_stop_triggered = False
        self._topic_to_event_map: Mapping[str, str] = {}
        self.identifier = identifier

    def register(self, event_name: str) -> Callable[[TEventHandler], Any]:
        def wrapper(handler: TEventHandler):
            self.logger.warning(
                f'🐼 [{self.identifier}] Register handler for "{event_name}"'
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
            if self.consumer is None:
                await self._connect()
            await self._init_topics()
            topics = list(self._topic_to_event_map.keys())
            self.logger.warning(f"🐼 [{self.identifier}] Subscribe to topics: {topics}")
            self.consumer.subscribe(topics=topics)
            async for message in self.consumer:
                topic_name = message.topic
                event_name = self._topic_to_event_map[topic_name]
                message_handler = self._handlers.get(event_name)
                decoded_value = self.serializer.decode(event_name, message.value)
                self.logger.info(
                    f'🐼 [{self.identifier}] Consume from "{topic_name}": '
                    + f"{decoded_value}"
                )
                await self._run_handler(message_handler, decoded_value)
            retry = self.retry
        except (asyncio.CancelledError, GeneratorExit, Exception) as e:
            if retry > 0:
                self.logger.error(f"🐼 [{self.identifier}]", exc_info=True)
            if retry == 0:
                self.logger.error(
                    f"🐼 [{self.identifier}] Failed to consume message after "
                    + f"{self.retry} attempts"
                )
                self.logger.fatal(f"🐼 [{self.identifier}] Cannot retry")
                raise e
            self.logger.warning(f"🐼 [{self.identifier}] Retry to consume")
            await self._disconnect()
            await asyncio.sleep(self.retry_interval)
            await self._start(retry - 1)
        finally:
            await self._disconnect()

    async def _init_topics(self):
        event_names = self._handlers.keys()
        await self.kafka_admin.create_events(event_names)
        self._topic_to_event_map = {
            event_name: self.kafka_admin.get_topic_name(event_name)
            for event_name in event_names
        }

    async def _connect(self):
        self.logger.info(f"🐼 [{self.identifier}] Create kafka consumer")
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
        self.logger.info(f"🐼 [{self.identifier}] Start kafka consumer")
        await self.consumer.start()
        self.logger.info(f"🐼 [{self.identifier}] Kafka consumer started")

    async def _disconnect(self):
        if self.consumer is not None:
            try:
                self.logger.info(
                    f"🐼 [{self.identifier}] Unsubscribe kafka consumer "
                    + "from all topics"
                )
                self.consumer.unsubscribe()
                self.logger.info(f"🐼 [{self.identifier}] Stop kafka consumer")
                await self.consumer.stop()
                self.logger.info(f"🐼 [{self.identifier}] Kafka consumer stopped")
            except (asyncio.CancelledError, GeneratorExit, Exception):
                self.logger.error(f"🐼 [{self.identifier}]", exc_info=True)
        self.consumer = None

    async def _run_handler(self, message_handler: TEventHandler, decoded_value: Any):
        if inspect.iscoroutinefunction(message_handler):
            return asyncio.create_task(message_handler(decoded_value))
        return message_handler(decoded_value)
