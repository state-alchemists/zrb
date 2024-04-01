from component.messagebus import (
    Admin,
    Consumer,
    KafkaAdmin,
    KafkaConsumer,
    KafkaPublisher,
    MessageSerializer,
    MockAdmin,
    MockConsumer,
    MockPublisher,
    Publisher,
    RMQAdmin,
    RMQConsumer,
    RMQPublisher,
)
from config import (
    app_broker_type,
    app_kafka_bootstrap_servers,
    app_kafka_sasl_mechanism,
    app_kafka_sasl_pass,
    app_kafka_sasl_user,
    app_kafka_security_protocol,
    app_rmq_connection_string,
    zrb_app_name,
)
from integration.log import logger


def init_admin(default_admin: Admin) -> Admin:
    if app_broker_type == "rabbitmq":
        return RMQAdmin(
            logger=logger, connection_string=app_rmq_connection_string, configs={}
        )
    if app_broker_type == "kafka":
        return KafkaAdmin(
            logger=logger,
            bootstrap_servers=app_kafka_bootstrap_servers,
            security_protocol=app_kafka_security_protocol,
            sasl_mechanism=app_kafka_sasl_mechanism,
            sasl_plain_username=app_kafka_sasl_user,
            sasl_plain_password=app_kafka_sasl_pass,
            configs={},
        )
    return default_admin


def init_publisher(
    serializer: MessageSerializer, admin: Admin, default_publisher: Publisher
) -> Publisher:
    if app_broker_type == "rabbitmq":
        return RMQPublisher(
            logger=logger,
            connection_string=app_rmq_connection_string,
            serializer=serializer,
            rmq_admin=admin,
        )
    if app_broker_type == "kafka":
        return KafkaPublisher(
            logger=logger,
            bootstrap_servers=app_kafka_bootstrap_servers,
            security_protocol=app_kafka_security_protocol,
            sasl_mechanism=app_kafka_sasl_mechanism,
            sasl_plain_username=app_kafka_sasl_user,
            sasl_plain_password=app_kafka_sasl_pass,
            serializer=serializer,
            kafka_admin=admin,
        )
    return default_publisher


def init_consumer(
    serializer: MessageSerializer, admin: Admin, default_consumer: Consumer
) -> Consumer:
    if app_broker_type == "rabbitmq":
        return RMQConsumer(
            logger=logger,
            connection_string=app_rmq_connection_string,
            serializer=serializer,
            rmq_admin=admin,
        )
    if app_broker_type == "kafka":
        return KafkaConsumer(
            logger=logger,
            bootstrap_servers=app_kafka_bootstrap_servers,
            security_protocol=app_kafka_security_protocol,
            sasl_mechanism=app_kafka_sasl_mechanism,
            sasl_plain_username=app_kafka_sasl_user,
            sasl_plain_password=app_kafka_sasl_pass,
            group_id=zrb_app_name,
            serializer=serializer,
            kafka_admin=admin,
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
    serializer=message_serializer, admin=admin, default_publisher=mock_publisher
)
