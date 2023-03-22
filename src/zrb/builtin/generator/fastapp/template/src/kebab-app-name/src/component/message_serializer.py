from core.messagebus.messagebus import MessageSerializer


def init_message_serializer() -> MessageSerializer:
    # Add custom logic if necessary
    return MessageSerializer()


message_serializer = init_message_serializer()
