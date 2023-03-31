from config import (
    app_name, app_broker_type, app_rmq_connection_string,
    app_kafka_bootstrap_servers
)
from core.messagebus.mock import MockConsumer, MockPublisher
from core.messagebus.messagebus import Consumer, MessageSerializer, Publisher
from core.messagebus.rabbitmq.consumer import RMQConsumer
from core.messagebus.kafka.consumer import KafkaConsumer
from core.messagebus.kafka.publisher import KafkaPublisher
from core.messagebus.rabbitmq.publisher import RMQPublisher
from component.log import logger


def init_publisher(
    broker_type: str,
    serializer: MessageSerializer,
    default_publisher: Publisher
) -> Publisher:
    if broker_type == 'rabbitmq':
        return RMQPublisher(
            logger=logger,
            connection_string=app_rmq_connection_string,
            serializer=serializer
        )
    if broker_type == 'kafka':
        return KafkaPublisher(
            logger=logger,
            bootstrap_servers=app_kafka_bootstrap_servers,
            serializer=serializer
        )
    if broker_type != 'mock':
        logger.warning(f'Invalid broker type {broker_type}')
    return default_publisher


def init_consumer(
    broker_type: str,
    serializer: MessageSerializer,
    default_consumer: Consumer
) -> Consumer:
    if broker_type == 'rabbitmq':
        return RMQConsumer(
            logger=logger,
            connection_string=app_rmq_connection_string,
            serializer=serializer
        )
    if broker_type == 'kafka':
        return KafkaConsumer(
            logger=logger,
            bootstrap_servers=app_kafka_bootstrap_servers,
            group_id=app_name,
            serializer=serializer
        )
    if broker_type != 'mock':
        logger.warning(f'Invalid broker type {broker_type}')
    return default_consumer


def init_message_serializer() -> MessageSerializer:
    # Add custom logic if necessary
    return MessageSerializer()


message_serializer = init_message_serializer()
mock_consumer = MockConsumer(logger, message_serializer)
mock_publisher = MockPublisher(logger, mock_consumer, message_serializer)
consumer = init_consumer(app_broker_type, message_serializer, mock_consumer)
publisher = init_publisher(app_broker_type, message_serializer, mock_publisher)
