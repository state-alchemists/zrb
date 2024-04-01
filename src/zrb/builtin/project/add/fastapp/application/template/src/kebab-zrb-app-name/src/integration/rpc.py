from component.messagebus import KafkaConsumer, RMQConsumer
from component.rpc import Caller, MessagebusCaller, MessagebusServer, Server
from config import (
    app_broker_type,
    app_kafka_bootstrap_servers,
    app_rmq_connection_string,
    zrb_app_name,
)
from integration.log import logger
from integration.messagebus import (
    admin,
    consumer,
    message_serializer,
    mock_consumer,
    publisher,
)
from ulid import ULID


def create_consumer():
    if app_broker_type == "rabbitmq":
        return RMQConsumer(
            logger=logger,
            connection_string=app_rmq_connection_string,
            serializer=message_serializer,
            rmq_admin=admin,
            identifier="rmq-rpc-reply-consumer",
        )
    if app_broker_type == "kafka":
        random_uuid = str(ULID())
        group_id = f"{zrb_app_name}-reply-{random_uuid}"
        return KafkaConsumer(
            logger=logger,
            bootstrap_servers=app_kafka_bootstrap_servers,
            group_id=group_id,
            serializer=message_serializer,
            kafka_admin=admin,
            identifier="kafka-rpc-reply-consumer",
        )
    return mock_consumer


rpc_caller: Caller = MessagebusCaller(
    logger=logger, admin=admin, publisher=publisher, consumer_factory=create_consumer
)

rpc_server: Server = MessagebusServer(
    logger=logger, consumer=consumer, publisher=publisher
)
