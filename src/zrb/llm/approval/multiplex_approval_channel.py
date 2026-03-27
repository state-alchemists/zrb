import asyncio
import sys

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
        self._pending: dict[str, asyncio.Future[ApprovalResult]] = {}
        self._tasks: dict[str, list[asyncio.Task]] = {}

    async def request_approval(self, context: ApprovalContext) -> ApprovalResult:
        if is_shutdown_requested():
            return ApprovalResult(approved=False, message="Shutdown requested")

        print(f"[DEBUG Multiplex] request_approval START for {context.tool_name}")
        print(
            f"[DEBUG Multiplex] Channels: {[type(c).__name__ for c in self._channels]}"
        )

        if not self._channels:
            print(f"[DEBUG Multiplex] No channels, auto-approving")
            return ApprovalResult(approved=True)

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
            except asyncio.CancelledError:
                print(f"[DEBUG Multiplex] Channel {type(channel).__name__} cancelled")
                raise
            except BaseException as e:
                import traceback

                print(
                    f"[DEBUG Multiplex] Channel {type(channel).__name__} Exception: {type(e).__name__}: {e}"
                )
                traceback.print_exc()
                if not future.done():
                    # Set exception result so other channels can continue
                    future.set_result(
                        ApprovalResult(approved=False, message=f"Channel error: {e}")
                    )
                return None

        # Run ALL channels concurrently - first response wins
        tasks = []
        for channel in self._channels:
            task = asyncio.create_task(request_from_channel(channel))
            tasks.append(task)
        self._tasks[context.tool_call_id] = tasks

        print(f"[DEBUG Multiplex] Racing {len(tasks)} channels concurrently...")

        try:
            # Wait for the first channel to complete (or all to fail)
            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )

            print(
                f"[DEBUG Multiplex] Race complete, {len(done)} done, {len(pending)} pending"
            )

            # Cancel pending tasks
            for task in pending:
                print(f"[DEBUG Multiplex] Cancelling pending task")
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            # Get result from the first completed task
            for task in done:
                try:
                    result = task.result()
                    # Wait for future to be set if needed
                    if result is None:
                        break
                    print(
                        f"[DEBUG Multiplex] Returning result: approved={result.approved}, message={result.message}"
                    )
                    return result
                except asyncio.CancelledError:
                    continue
                except Exception as e:
                    print(f"[DEBUG Multiplex] Task exception: {e}")
                    continue
        except asyncio.CancelledError:
            print(f"[DEBUG Multiplex] request_approval cancelled externally")
            raise

        # If we got here, wait for future to be set (e.g., by an external callback)
        print(f"[DEBUG Multiplex] Waiting for future to be set...")
        try:
            result = await future
            print(f"[DEBUG Multiplex] Future resolved: approved={result.approved}")
            return result
        except asyncio.CancelledError:
            print(f"[DEBUG Multiplex] Future wait cancelled")
            raise

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
