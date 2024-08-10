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
    APP_BROKER_TYPE,
    APP_KAFKA_BOOTSTRAP_SERVERS,
    APP_KAFKA_SASL_MECHANISM,
    APP_KAFKA_SASL_PASS,
    APP_KAFKA_SASL_USER,
    APP_KAFKA_SECURITY_PROTOCOL,
    APP_NAME,
    APP_RMQ_CONNECTION_STRING,
)
from integration.log import logger


def init_admin(default_admin: Admin) -> Admin:
    if APP_BROKER_TYPE == "rabbitmq":
        return RMQAdmin(
            logger=logger, connection_string=APP_RMQ_CONNECTION_STRING, configs={}
        )
    if APP_BROKER_TYPE == "kafka":
        return KafkaAdmin(
            logger=logger,
            bootstrap_servers=APP_KAFKA_BOOTSTRAP_SERVERS,
            security_protocol=APP_KAFKA_SECURITY_PROTOCOL,
            sasl_mechanism=APP_KAFKA_SASL_MECHANISM,
            sasl_plain_username=APP_KAFKA_SASL_USER,
            sasl_plain_password=APP_KAFKA_SASL_PASS,
            configs={},
        )
    return default_admin


def init_publisher(
    serializer: MessageSerializer, admin: Admin, default_publisher: Publisher
) -> Publisher:
    if APP_BROKER_TYPE == "rabbitmq":
        return RMQPublisher(
            logger=logger,
            connection_string=APP_RMQ_CONNECTION_STRING,
            serializer=serializer,
            rmq_admin=admin,
        )
    if APP_BROKER_TYPE == "kafka":
        return KafkaPublisher(
            logger=logger,
            bootstrap_servers=APP_KAFKA_BOOTSTRAP_SERVERS,
            security_protocol=APP_KAFKA_SECURITY_PROTOCOL,
            sasl_mechanism=APP_KAFKA_SASL_MECHANISM,
            sasl_plain_username=APP_KAFKA_SASL_USER,
            sasl_plain_password=APP_KAFKA_SASL_PASS,
            serializer=serializer,
            kafka_admin=admin,
        )
    return default_publisher


def init_consumer(
    serializer: MessageSerializer, admin: Admin, default_consumer: Consumer
) -> Consumer:
    if APP_BROKER_TYPE == "rabbitmq":
        return RMQConsumer(
            logger=logger,
            connection_string=APP_RMQ_CONNECTION_STRING,
            serializer=serializer,
            rmq_admin=admin,
        )
    if APP_BROKER_TYPE == "kafka":
        return KafkaConsumer(
            logger=logger,
            bootstrap_servers=APP_KAFKA_BOOTSTRAP_SERVERS,
            security_protocol=APP_KAFKA_SECURITY_PROTOCOL,
            sasl_mechanism=APP_KAFKA_SASL_MECHANISM,
            sasl_plain_username=APP_KAFKA_SASL_USER,
            sasl_plain_password=APP_KAFKA_SASL_PASS,
            group_id=APP_NAME,
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
