from config import (
    app_broker_type, app_rmq_connection, app_kafka_bootstrap_servers
)
from core.messagebus.messagebus import Publisher, MessageSerializer
from core.messagebus.kafka.publisher import (
    KafkaPublishConnection, KafkaPublisher
)
from core.messagebus.rabbitmq.publisher import (
    RMQPublishConnection, RMQPublisher
)
from component.message_mocker import mock_publisher
from component.message_serializer import message_serializer
from component.log import logger


def init_publisher(
    broker_type: str, serializer: MessageSerializer
) -> Publisher:
    if broker_type == 'rabbitmq':
        publish_connection = RMQPublishConnection(
            logger=logger, connection_string=app_rmq_connection
        )
        return RMQPublisher(
            logger=logger,
            publish_connection=publish_connection,
            serializer=serializer
        )
    if broker_type == 'kafka':
        publish_connection = KafkaPublishConnection(
            logger=logger, bootstrap_servers=app_kafka_bootstrap_servers
        )
        return KafkaPublisher(
            logger=logger,
            publish_connection=publish_connection,
            serializer=serializer
        )
    if broker_type == 'mock':
        return mock_publisher
    raise Exception(f'Invalid broker type: {broker_type}')


publisher = init_publisher(app_broker_type, message_serializer)
