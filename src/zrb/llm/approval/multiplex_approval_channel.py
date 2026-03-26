import asyncio
import json
import sys

from zrb.llm.approval.approval_channel import (
    ApprovalChannel,
    ApprovalContext,
    ApprovalResult,
)


class MultiplexApprovalChannel(ApprovalChannel):
    """Approval channel that broadcasts approval requests to multiple channels.

    The first response wins and cancels pending requests on other channels.

    Usage:
        channel = MultiplexApprovalChannel([
            TerminalApprovalChannel(),
            TelegramApprovalChannel(bot, chat_id),
        ])
        llm_chat.set_approval_channel(channel)
    """

    def __init__(self, channels: list[ApprovalChannel]):
        self._channels = channels
        self._pending: dict[str, asyncio.Future[ApprovalResult]] = {}
        self._tasks: dict[str, list[asyncio.Task]] = {}

    async def request_approval(self, context: ApprovalContext) -> ApprovalResult:
        if is_shutdown_requested():
            return ApprovalResult(approved=False, message="Shutdown requested")

        print(f"[DEBUG Multiplex] request_approval START for {context.tool_name}")
        print(
            f"[DEBUG Multiplex] Channels: {[type(c).__name__ for c in self._channels]}"
        )

        loop = asyncio.get_running_loop()
        future: asyncio.Future[ApprovalResult] = loop.create_future()
        self._pending[context.tool_call_id] = future
        self._tasks[context.tool_call_id] = []

        async def request_from_channel(channel: ApprovalChannel):
            try:
                print(f"[DEBUG Multiplex] Calling channel {type(channel).__name__}...")
                result = await channel.request_approval(context)
                print(
                    f"[DEBUG Multiplex] Channel {type(channel).__name__} returned: approved={result.approved}"
                )
                if not future.done():
                    print(f"[DEBUG Multiplex] Setting future result: {result}")
                    future.set_result(result)
                return result
            except BaseException as e:
                import traceback

                print(
                    f"[DEBUG Multiplex] Channel {type(channel).__name__} Exception: {type(e).__name__}: {e}"
                )
                # Don't propagate - just wait
                traceback.print_exc()
                # Wait for another channel
                return None

        # Run channels sequentially to avoid telegram polling conflicts
        for ch in self._channels:
            print(f"[DEBUG Multiplex] Processing channel: {type(ch).__name__}")
            result = await request_from_channel(ch)
            if result is not None:
                print(
                    f"[DEBUG Multiplex] Returning result: approved={result.approved}, message={result.message}"
                )
                return result
            print(f"[DEBUG Multiplex] Channel returned None, trying next channel...")

        # If we got here, all channels failed - wait indefinitely for user input
        print(f"[DEBUG Multiplex] All channels failed, waiting for user input...")
        while not future.done():
            await asyncio.sleep(1)
        return future.result()

    async def notify(
        self, message: str, context: ApprovalContext | None = None
    ) -> None:
        if is_shutdown_requested():
            return
        for channel in self._channels:
            try:
                await channel.notify(message, context)
            except Exception:
                pass


def is_shutdown_requested() -> bool:
    return getattr(sys, "_zrb_shutdown_requested", False)
