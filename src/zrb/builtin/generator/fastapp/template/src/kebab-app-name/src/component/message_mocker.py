from core.messagebus.mock import MockConsumer, MockPublisher
from component.message_serializer import message_serializer
from component.log import logger

mock_consumer = MockConsumer(logger, message_serializer)
mock_publisher = MockPublisher(logger, mock_consumer, message_serializer)
