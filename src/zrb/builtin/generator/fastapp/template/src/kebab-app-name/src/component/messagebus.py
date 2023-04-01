from config import (
    app_name, app_broker_type, app_rmq_connection_string,
    app_kafka_bootstrap_servers
)
from core.messagebus.mock import MockAdmin, MockConsumer, MockPublisher
from core.messagebus.messagebus import (
    Admin, Consumer, MessageSerializer, Publisher
)
from core.messagebus.kafka.admin import KafkaAdmin
from core.messagebus.kafka.consumer import KafkaConsumer
from core.messagebus.kafka.publisher import KafkaPublisher
from core.messagebus.rabbitmq.admin import RMQAdmin
from core.messagebus.rabbitmq.consumer import RMQConsumer
from core.messagebus.rabbitmq.publisher import RMQPublisher
from component.log import logger


def init_admin(
    default_admin: Admin
) -> Admin:
    if app_broker_type == 'rabbitmq':
        return RMQAdmin(
            logger=logger,
            connection_string=app_rmq_connection_string,
            configs={}
        )
    if app_broker_type == 'kafka':
        return KafkaAdmin(
            logger=logger,
            bootstrap_servers=app_kafka_bootstrap_servers,
            configs={}
        )
    return default_admin


def init_publisher(
    serializer: MessageSerializer,
    admin: Admin,
    default_publisher: Publisher
) -> Publisher:
    if app_broker_type == 'rabbitmq':
        return RMQPublisher(
            logger=logger,
            connection_string=app_rmq_connection_string,
            serializer=serializer,
            rmq_admin=admin
        )
    if app_broker_type == 'kafka':
        return KafkaPublisher(
            logger=logger,
            bootstrap_servers=app_kafka_bootstrap_servers,
            serializer=serializer,
            kafka_admin=admin
        )
    return default_publisher


def init_consumer(
    serializer: MessageSerializer,
    admin: Admin,
    default_consumer: Consumer
) -> Consumer:
    if app_broker_type == 'rabbitmq':
        return RMQConsumer(
            logger=logger,
            connection_string=app_rmq_connection_string,
            serializer=serializer,
            rmq_admin=admin
        )
    if app_broker_type == 'kafka':
        return KafkaConsumer(
            logger=logger,
            bootstrap_servers=app_kafka_bootstrap_servers,
            group_id=app_name,
            serializer=serializer,
            kafka_admin=admin
        )
    return default_consumer


def init_message_serializer() -> MessageSerializer:
    # Add custom logic if necessary
    return MessageSerializer()


message_serializer = init_message_serializer()
mock_admin = MockAdmin()
mock_consumer = MockConsumer(logger=logger, serializer=message_serializer)
mock_publisher = MockPublisher(
    logger=logger, consumer=mock_consumer, serializer=message_serializer
)
admin = init_admin(default_admin=mock_admin)
consumer = init_consumer(
    serializer=message_serializer, admin=admin, default_consumer=mock_consumer
)
publisher = init_publisher(
    serializer=message_serializer,
    admin=admin,
    default_publisher=mock_publisher
)
