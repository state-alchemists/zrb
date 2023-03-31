from typing import Any, Mapping
from core.messagebus.messagebus import Consumer, Publisher
from core.rpc.rpc import Server, TRPCHandler, Message
import logging


class MbServer(Server):

    def __init__(
        self, logger: logging.Logger,
        consumer: Consumer,
        publisher: Publisher
    ):
        self.logger = logger
        self.consumer = consumer
        self.publisher = publisher

    async def start(self):
        await self.consumer.start()

    async def stop(self):
        await self.consumer.stop()

    def register(self, rpc_name):
        def wrapper(handler: TRPCHandler):
            @self.consumer.register(rpc_name)
            def event_handler(message_dict: Mapping[str, Any]):
                message: Message = Message.from_dict(message_dict)
                args = message.args
                kwargs = message.kwargs
                reply_event = message.reply_event
                result = handler(*args, **kwargs)
                self.publisher.publish(reply_event, result)
        return wrapper
