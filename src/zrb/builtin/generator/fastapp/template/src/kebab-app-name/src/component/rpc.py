from core.rpc.rpc import Caller, Server
from core.rpc.messagebus.caller import MessagebusCaller
from core.rpc.messagebus.server import MessagebusServer
from core.messagebus.rabbitmq.consumer import RMQConsumer
from core.messagebus.kafka.consumer import KafkaConsumer
from component.messagebus import (
    admin, consumer, publisher, message_serializer, mock_consumer
)
from component.log import logger
from config import (
    app_name, app_broker_type, app_rmq_connection_string,
    app_kafka_bootstrap_servers
)
import uuid


def create_consumer():
    if app_broker_type == 'rabbitmq':
        return RMQConsumer(
            logger=logger,
            connection_string=app_rmq_connection_string,
            serializer=message_serializer,
            rmq_admin=admin,
            identifier='rmq-rpc-reply-consumer'
        )
    if app_broker_type == 'kafka':
        random_uuid = str(uuid.uuid4())
        group_id = f'{app_name}-reply-{random_uuid}'
        return KafkaConsumer(
            logger=logger,
            bootstrap_servers=app_kafka_bootstrap_servers,
            group_id=group_id,
            serializer=message_serializer,
            kafka_admin=admin,
            identifier='kafka-rpc-reply-consumer'
        )
    return mock_consumer


rpc_caller: Caller = MessagebusCaller(
    logger=logger,
    admin=admin,
    publisher=publisher,
    consumer_factory=create_consumer
)

rpc_server: Server = MessagebusServer(
    logger=logger,
    consumer=consumer,
    publisher=publisher
)
