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

        loop = asyncio.get_running_loop()
        future: asyncio.Future[ApprovalResult] = loop.create_future()
        self._pending[context.tool_call_id] = future
        self._tasks[context.tool_call_id] = []

        async def request_from_channel(channel: ApprovalChannel):
            try:
                result = await channel.request_approval(context)
                if not future.done():
                    future.set_result(result)
                return result
            except Exception as e:
                if not future.done():
                    future.set_result(ApprovalResult(approved=False, message=str(e)))
                return ApprovalResult(approved=False, message=str(e))

        for ch in self._channels:
            task = asyncio.create_task(request_from_channel(ch))
            self._tasks[context.tool_call_id].append(task)

        try:
            async with asyncio.timeout(300):
                return await future
        except asyncio.TimeoutError:
            return ApprovalResult(approved=False, message="Timeout")
        finally:
            for task in self._tasks.pop(context.tool_call_id, []):
                task.cancel()
            self._pending.pop(context.tool_call_id, None)

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
