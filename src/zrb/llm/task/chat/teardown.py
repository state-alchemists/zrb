"""Releasing what an interactive chat holds, while its event loop is still alive.

Six steps, and three of them release process-global singletons: the session's
hook manager, the LSP servers, the hook executor's worker threads, and the
shell and delegation registries. They run here rather than from an `atexit`
backstop because those run too late for a graceful shutdown.

Interactive only. The web/SSE runner reuses the non-interactive path per
message, and tearing that down would kill work another session still needs.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.llm.hook.contracts.types import HookEvent
from zrb.llm.hook.execution import executor as hook_executor
from zrb.llm.hook.manager import hook_manager
from zrb.llm.lsp.manager.manager import lsp_manager
from zrb.llm.shared.ambient_state import (
    get_current_tool_session,
    get_session_ownership_key,
)
from zrb.llm.shared.feature_config import close_feature_sessions
from zrb.llm.tool.delegate.background import get_background_registry
from zrb.llm.tool.shell.background import get_shell_background_registry
from zrb.util.async_thread import run_in_daemon

if TYPE_CHECKING:
    from zrb.llm.task.chat.task import LLMChatTask

# How long a feature gets to close at exit before it is left to the process.
_FEATURE_CLOSE_SECONDS = 3.0


async def release_chat_resources(llm_chat_task: "LLMChatTask") -> None:
    """Release every process-global resource an interactive chat holds.

    Held against cancellation: a Ctrl+C cancels the main task, and cutting this
    short would strand language servers and detached hooks. The cancellation is
    re-raised once the last step ends.
    """
    release = asyncio.ensure_future(_release_all(llm_chat_task))
    cancellation: asyncio.CancelledError | None = None
    while not release.done():
        try:
            await asyncio.shield(release)
        except asyncio.CancelledError as exc:
            cancellation = exc
    release.result()
    if cancellation is not None:
        raise cancellation


async def settle_background_hooks(
    llm_chat_task: "LLMChatTask", drain_seconds: float | None = None
) -> None:
    """Settle this run's detached (``async: true``) hooks.

    Detached hooks sit in their own process group, so nothing else reaps them.
    ``drain=True`` lets just-dispatched hooks finish, for up to *drain_seconds*
    (the hook manager's default when ``None``), before stragglers are cancelled.
    Falls back to the module singleton when no per-run manager was created,
    matching ``run_agent``.
    """
    try:
        if llm_chat_task.active_hook_manager is not None:
            await llm_chat_task.active_hook_manager.shutdown(
                drain=True, drain_seconds=drain_seconds
            )
            return
        await hook_manager.shutdown(drain=True, drain_seconds=drain_seconds)
    except Exception as e:
        CFG.LOGGER.debug(f"Background-hook shutdown at teardown failed: {e}")


async def _release_all(llm_chat_task: "LLMChatTask") -> None:
    # One budget for every hook this quit waits on: SESSION_END, then the
    # detached hooks still running. Summed per-stage limits let one slow
    # SessionEnd hook hold the terminal for its own timeout (600 s).
    deadline = time.monotonic() + CFG.HOOKS_EXIT_TIMEOUT / 1000
    await _fire_session_end(llm_chat_task, deadline)
    # A feature's close can block for good, so it runs off this thread.
    await _close_feature_sessions(deadline)
    await _shutdown_language_servers()
    # Settle detached hooks before releasing the worker pool, so their
    # cancellation handlers can kill process trees that sit in their own
    # process group and never see the terminal's Ctrl+C.
    await settle_background_hooks(llm_chat_task, _seconds_left(deadline))
    # Reap background subprocesses while the loop is alive; otherwise their
    # exit logs "Loop <...> that handles pid N is closed".
    await _cancel_background_work()
    _shutdown_hook_executor()
    # Nothing runs after this, so the manager is cleared: a second teardown
    # would otherwise fire SESSION_END on a run that has already ended.
    llm_chat_task.active_hook_manager = None


async def _fire_session_end(llm_chat_task: "LLMChatTask", deadline: float) -> None:
    """Fire SESSION_END once, within what is left of the exit budget.

    `run_agent` fires only STOP per turn, so this is the session's one terminal
    event. Every exit cause funnels through here, which is why it is "other".
    """
    if llm_chat_task.active_hook_manager is None:
        return
    try:
        await asyncio.wait_for(
            llm_chat_task.active_hook_manager.execute_hooks(
                HookEvent.SESSION_END,
                {"reason": "exit"},
                source="other",
            ),
            timeout=_seconds_left(deadline),
        )
    except asyncio.TimeoutError:
        CFG.LOGGER.warning(
            "A SessionEnd hook was still running at exit; cancelling it."
        )
    except Exception:
        CFG.LOGGER.debug("SESSION_END hook raised at teardown", exc_info=True)


async def _close_feature_sessions(deadline: float) -> None:
    """Close this session's features before the loop goes, off its thread.

    Their closes are synchronous and block for good more readily than most
    calls: a wedged audio device holds a stream's stop, a model being unloaded
    holds the backend behind it. Run on the loop's thread, that also freezes the
    rest of the quit, and Ctrl+C is only handled back in Python, so the process
    reads as hung. One still going at the deadline is logged and left to the
    process.
    """
    try:
        await asyncio.wait_for(
            run_in_daemon(
                close_feature_sessions,
                get_session_ownership_key(),
                name="zrb-close-features",
            ),
            timeout=min(_FEATURE_CLOSE_SECONDS, _seconds_left(deadline)),
        )
    except asyncio.TimeoutError:
        CFG.LOGGER.warning(
            "A feature was still closing at exit; leaving it to the process."
        )
    except Exception:
        CFG.LOGGER.debug("Closing feature sessions failed", exc_info=True)


async def _shutdown_language_servers() -> None:
    try:
        await lsp_manager.shutdown_all()
    except Exception as e:
        CFG.LOGGER.debug(f"LSP shutdown at session end failed: {e}")


async def _cancel_background_work() -> None:
    """Kill the background shells and delegation sub-agents this quit owns."""
    try:
        # Every shell this process started, not one session's: a background
        # shell carries the web session that started it and "" for an
        # interactive one, so an interactive quit owns them all. The delegation
        # registry below is keyed for the opposite reason, and says so.
        await get_shell_background_registry().cancel_all()
    except Exception as e:
        CFG.LOGGER.debug(f"Background-shell teardown at session end failed: {e}")
    try:
        # This session's own handles only: the registry is process-wide, and
        # another chat session's delegation must outlive this one's exit.
        get_background_registry().cancel_all(
            get_session_ownership_key(get_current_tool_session())
        )
    except Exception as e:
        CFG.LOGGER.debug(f"Background-delegation teardown at session end failed: {e}")


def _shutdown_hook_executor() -> None:
    try:
        hook_executor.shutdown_hook_executor(wait=False)
    except Exception as e:
        CFG.LOGGER.debug(f"Hook-executor shutdown at session end failed: {e}")


def _seconds_left(deadline: float) -> float:
    return max(0.0, deadline - time.monotonic())
