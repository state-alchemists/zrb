import asyncio
import logging
from typing import Any, Callable

from component.messagebus.messagebus import Admin, Consumer, Publisher
from component.rpc.rpc import Caller, Message, Result
from ulid import ULID


class MessagebusCaller(Caller):
    def __init__(
        self,
        logger: logging.Logger,
        admin: Admin,
        publisher: Publisher,
        consumer_factory: Callable[[], Consumer],
        timeout: float = 30,
        check_reply_interval: float = 0.1,
    ):
        self.logger = logger
        self.admin = admin
        self.publisher = publisher
        self.consumer_factory = consumer_factory
        self.timeout = timeout
        self.check_reply_interval = check_reply_interval

    async def call(self, rpc_name: str, *args: Any, **kwargs: Any):
        random_uuid = str(ULID())
        reply_event_name = f"reply_{rpc_name}_{random_uuid}"
        await self.admin.create_events([reply_event_name])
        reply_consumer = self.consumer_factory()
        reply_received_event = asyncio.Event()
        call_result, call_error = None, None

        @reply_consumer.register(reply_event_name)
        async def consume_reply(result_dict: Any):
            nonlocal call_result, call_error
            result = Result.from_dict(result_dict)
            call_result, call_error = result.result, result.error
            reply_received_event.set()
            await reply_consumer.stop()

        try:
            task = asyncio.create_task(reply_consumer.start())
            await self.publisher.publish(
                rpc_name,
                Message(
                    reply_event=reply_event_name, args=args, kwargs=kwargs
                ).to_dict(),
            )
            await asyncio.gather(task)
            await asyncio.wait_for(reply_received_event.wait(), timeout=self.timeout)
        except asyncio.TimeoutError:
            self.logger.error(
                "🤙 [messagebus-rpc-caller] "
                + f"Timeout while waiting for reply event {reply_event_name}"
            )
            raise Exception(
                f"Timeout while waiting for reply event: {reply_event_name}"
            )
        finally:
            await self._clean_up(reply_consumer, reply_event_name)
        # raise call_error or return call_result
        if call_error != "":
            self.logger.error(
                "🤙 [messagebus-rpc-caller] RPC "
                + f'"{rpc_name}" returning error: {call_error}'
            )
            raise Exception(call_error)
        self.logger.info(
            "🤙 [messagebus-rpc-caller] RPC "
            + f'"{rpc_name}" returning result: {call_result}'
        )
        return call_result

    async def _clean_up(self, reply_consumer: Consumer, reply_event_name: str):
        try:
            await reply_consumer.stop()
        except (asyncio.CancelledError, GeneratorExit, Exception):
            self.logger.error("🤙 [messagebus-rpc-caller]", exc_info=True)
        try:
            await self.admin.delete_events([reply_event_name])
        except (asyncio.CancelledError, GeneratorExit, Exception):
            self.logger.error("🤙 [messagebus-rpc-caller]", exc_info=True)
