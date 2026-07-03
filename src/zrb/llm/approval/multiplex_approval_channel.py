import asyncio
import sys
import traceback

from zrb.config.config import CFG
from zrb.llm.approval.approval_channel import (
    ApprovalChannel,
    ApprovalContext,
    ApprovalResult,
)


class MultiplexApprovalChannel(ApprovalChannel):
    """Approval channel that broadcasts approval requests to multiple channels.

    All channels receive the approval request simultaneously.
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

    async def request_approval(self, context: ApprovalContext) -> ApprovalResult:
        if is_shutdown_requested():
            return ApprovalResult(approved=False, message="Shutdown requested")

        CFG.LOGGER.debug(f"Multiplex request_approval START for {context.tool_name}")

        if not self._channels:
            CFG.LOGGER.debug("Multiplex No channels, auto-approving")
            return ApprovalResult(approved=True)

        loop = asyncio.get_running_loop()
        future: asyncio.Future[ApprovalResult] = loop.create_future()

        async def request_from_channel(channel: ApprovalChannel):
            try:
                result = await channel.request_approval(context)
                CFG.LOGGER.debug(
                    f"Multiplex Channel {type(channel).__name__} returned: "
                    f"approved={result.approved}"
                )
                if not future.done():
                    future.set_result(result)
            except asyncio.CancelledError:
                raise
            except BaseException as e:
                CFG.LOGGER.debug(
                    f"Multiplex Channel {type(channel).__name__} "
                    f"Exception: {type(e).__name__}: {e}"
                )
                traceback.print_exc()
                # A broken channel must NOT win the race: resolving the future
                # here would deny before the humans on the remaining channels
                # (e.g. the terminal) get a chance to answer. Denial happens
                # only in the watchdog, once EVERY channel has finished
                # without producing a result.

        # Race all channels; the first real response resolves the future.
        tasks = [
            asyncio.create_task(request_from_channel(channel))
            for channel in self._channels
        ]

        async def deny_when_all_channels_done():
            await asyncio.gather(*tasks, return_exceptions=True)
            if not future.done():
                future.set_result(
                    ApprovalResult(approved=False, message="All approval channels failed")
                )

        watchdog = asyncio.create_task(deny_when_all_channels_done())
        try:
            result = await future
            CFG.LOGGER.debug(
                f"Multiplex Returning result: approved={result.approved}, "
                f"message={result.message}"
            )
            return result
        finally:
            # Cancel the losers (and the watchdog) and reap them so nothing
            # outlives this request — no per-call state is retained.
            watchdog.cancel()
            for task in tasks:
                task.cancel()
            await asyncio.gather(watchdog, *tasks, return_exceptions=True)

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
    return getattr(sys, "zrb_shutdown_requested", False)
