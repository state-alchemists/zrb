from component.messagebus import KafkaConsumer, RMQConsumer
from component.rpc import Caller, MessagebusCaller, MessagebusServer, Server
from config import (
    APP_BROKER_TYPE,
    APP_KAFKA_BOOTSTRAP_SERVERS,
    APP_NAME,
    APP_RMQ_CONNECTION_STRING,
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
    if APP_BROKER_TYPE == "rabbitmq":
        return RMQConsumer(
            logger=logger,
            connection_string=APP_RMQ_CONNECTION_STRING,
            serializer=message_serializer,
            rmq_admin=admin,
            identifier="rmq-rpc-reply-consumer",
        )
    if APP_BROKER_TYPE == "kafka":
        random_uuid = str(ULID())
        group_id = f"{APP_NAME}-reply-{random_uuid}"
        return KafkaConsumer(
            logger=logger,
            bootstrap_servers=APP_KAFKA_BOOTSTRAP_SERVERS,
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
