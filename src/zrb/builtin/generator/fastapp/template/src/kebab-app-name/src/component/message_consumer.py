from config import (
    app_name, app_broker_type, app_rmq_connection, app_kafka_bootstrap_servers
)
from core.messagebus.messagebus import Consumer, MessageSerializer
from core.messagebus.rabbitmq.consumer import RMQConsumeConnection, RMQConsumer
from core.messagebus.kafka.consumer import (
    KafkaConsumeConnection, KafkaConsumer
)
from component.message_mocker import mock_consumer
from component.message_serializer import message_serializer
from component.log import logger


def init_consumer(
    broker_type: str, serializer: MessageSerializer
) -> Consumer:
    if broker_type == 'rabbitmq':
        consume_connection = RMQConsumeConnection(
            logger=logger, connection_string=app_rmq_connection
        )
        return RMQConsumer(
            logger=logger,
            consume_connection=consume_connection,
            serializer=serializer
        )
    if broker_type == 'kafka':
        consume_connection = KafkaConsumeConnection(
            logger=logger,
            bootstrap_servers=app_kafka_bootstrap_servers,
            group_id=app_name
        )
        return KafkaConsumer(
            logger=logger,
            consume_connection=consume_connection,
            serializer=serializer
        )
    if broker_type == 'mock':
        return mock_consumer
    raise Exception(f'Invalid broker type: {broker_type}')


consumer = init_consumer(app_broker_type, message_serializer)
