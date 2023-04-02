from typing import Any, Mapping
from core.messagebus.messagebus import Consumer, Publisher
from core.rpc.rpc import Server, TRPCHandler, Message
import logging
import inspect


class MessagebusServer(Server):

    def __init__(
        self,
        logger: logging.Logger,
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
            async def event_handler(message_dict: Mapping[str, Any]):
                message: Message = Message.from_dict(message_dict)
                args = message.args
                kwargs = message.kwargs
                reply_event = message.reply_event
                # get reply
                self.logger.info(
                    '🤙 [messagebus-rpc-server] ' +
                    f'Getting result for RPC: {rpc_name} ' +
                    f', args: {args} ' +
                    f', kwargs: {kwargs} ' +
                    f', reply_event: {reply_event}'
                )
                result = await self._run_handler(handler, *args, **kwargs)
                # publish reply
                await self.publisher.publish(reply_event, result)
        return wrapper

    async def _run_handler(
        self, handler: TRPCHandler, *args: Any, **kwargs: Any
    ):
        if inspect.iscoroutinefunction(handler):
            return await handler(*args, **kwargs)
        return handler(*args, **kwargs)
