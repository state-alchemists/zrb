"""Per-session chat loop: drains the SSE input queue, drives `LLMChatTask`.

Multiple SSE sessions share one `LLMChatTask` instance. For each message this
loop acquires `ChatSessionManager.task_lock`, points the task's public config
(`ui_factories`, `approval_channels`, `history_manager`, `include_default_ui`)
at the session's HTTP UI factory + approval channel, runs, then restores the
prior config — all inside the lock, so a concurrent session can never clobber
an in-flight run's wiring. The lock is held per message, not per session, so
sessions still coexist; they just don't drive the shared task simultaneously.
"""

from __future__ import annotations

import asyncio
import traceback
from typing import Any

from zrb.config.config import CFG
from zrb.context.shared_context import SharedContext
from zrb.llm.tool.ambient_state import current_chat_session_id
from zrb.runner.chat.chat_session_manager import ChatSession, ChatSessionManager
from zrb.runner.chat.http_ui import create_http_ui_factory
from zrb.session.session import Session
from zrb.util.contextvar_scope import scoped


async def run_chat_session(
    session: ChatSession,
    llm_chat_task: Any,
    session_manager: ChatSessionManager,
) -> None:
    """Drive an SSE chat session through `llm_chat_task` until cancelled."""
    current_task = asyncio.current_task()
    # Always set: this coroutine is itself running on an asyncio task.
    assert current_task is not None

    # The per-session UI factory / approval channel are independent objects — safe
    # to build once. The shared LLMChatTask is configured + driven under
    # `session_manager.task_lock` per message (snapshot → apply → run → restore via
    # the helpers below) so concurrent sessions never clobber each other's wiring.
    approval_channel = session.approval_channel
    http_ui_factory = create_http_ui_factory(
        session_manager,
        session.session_id,
        session.session_name,
        approval_channel,
    )

    try:
        session_manager.set_processing(session.session_id, False)

        while True:
            llm_task: asyncio.Task | None = None
            try:
                queued = await asyncio.wait_for(
                    session.input_queue.get(),
                    timeout=CFG.LLM_INPUT_QUEUE_TIMEOUT / 1000,
                )
            except asyncio.TimeoutError:
                if current_task.cancelling() > 0:
                    # wait_for's timeout raced with an external cancel() and
                    # consumed the CancelledError. Re-raising TimeoutError here
                    # would fall into the generic Exception handler below and
                    # the task would finish "successfully" despite being
                    # cancelled — surface it as a real cancellation instead.
                    raise asyncio.CancelledError()
                continue

            message = queued["message"]
            attachments = queued.get("attachments") or []

            session_manager.set_processing(session.session_id, True)
            CFG.LOGGER.info(f"Processing message: {message[:100]}")
            await session_manager.broadcast(session.session_id, f"[USER] {message}")

            shared_ctx = SharedContext(
                input={
                    "message": message,
                    "session": session.session_name,
                    "yolo": "false",
                    # Comma-joined paths, matching the CLI's `--attach` input
                    # convention that `llm_chat`'s `attachment=` lambda reads
                    # (`ctx.input.attach`, see `builtin/llm/chat.py`).
                    "attach": ",".join(attachments),
                    "model": "",
                    # Explicit: without this key the task falls back to the CLI
                    # input's default (True) and runs the *interactive* branch
                    # per message — replaying full history to the SSE client and
                    # tearing down LSP servers / firing SESSION_END hooks every turn.
                    "interactive": "false",
                }
            )
            session_obj = Session(shared_ctx=shared_ctx)
            try:
                # Hold the lock across configure+run+restore so an in-flight run
                # always sees this session's wiring.
                async with session_manager.task_lock:
                    saved = _snapshot_task_config(llm_chat_task)
                    _apply_session_config(
                        llm_chat_task,
                        history_manager=session_manager.history_manager,
                        ui_factory=http_ui_factory,
                        approval_channel=approval_channel,
                    )
                    try:
                        # Bound only around the spawn: asyncio.create_task
                        # copies the current context, so the task keeps this
                        # value for its whole run regardless of when this
                        # `with` block exits (see ADR-0069's "spawn inside the
                        # still-bound scope" invariant). Session.session_id is
                        # the unique key — never session_name, which
                        # ChatSessionManager never guarantees unique — so a
                        # background process this run starts can only ever be
                        # cleaned up by removing *this* session.
                        with scoped(current_chat_session_id, session.session_id):
                            llm_task = asyncio.create_task(
                                _run_llm_message(
                                    session_obj,
                                    CFG.LLM_REQUEST_TIMEOUT / 1000,
                                    llm_chat_task,
                                    session_manager,
                                    session.session_id,
                                )
                            )
                        await llm_task
                        CFG.LOGGER.info("LLM task completed")
                    except asyncio.CancelledError:
                        # Cancellation landed while awaiting the run. Awaiting a
                        # Task does NOT cancel it, so cancel explicitly and wait
                        # for it to unwind — otherwise the finally below restores
                        # the shared task's wiring underneath a still-running run.
                        if llm_task is not None and not llm_task.done():
                            llm_task.cancel()
                            try:
                                await llm_task
                            except asyncio.CancelledError:
                                pass
                            except Exception as unwind_error:
                                # Don't crash the cancel path, but a failure
                                # during unwind (e.g. history save) must not
                                # disappear silently either.
                                CFG.LOGGER.warning(
                                    f"LLM task error during cancel-unwind: "
                                    f"{unwind_error!r}"
                                )
                        raise
                    finally:
                        _apply_task_config(llm_chat_task, saved)
            except asyncio.CancelledError:
                session_manager.set_processing(session.session_id, False)
                raise
            except Exception as e:
                # _run_llm_message already broadcast the error to the client.
                # Keep the loop alive: one failed/timed-out request must not kill
                # the session, or every queued message sits unprocessed until the
                # browser happens to reopen the SSE stream.
                CFG.LOGGER.error(f"LLM task error: {e}")
                session_manager.set_processing(session.session_id, False)
                continue
            session_manager.set_processing(session.session_id, False)
    except asyncio.CancelledError:
        raise
    except Exception as e:
        error_msg = f"[ERROR] {str(e)}\n{traceback.format_exc()}\n"
        await session_manager.broadcast(session.session_id, error_msg)
    finally:
        session_manager.set_processing(session.session_id, False)


async def _run_llm_message(
    session_obj: Any,
    timeout: float,
    llm_chat_task: Any,
    session_manager: ChatSessionManager,
    session_id: str,
) -> None:
    """Run one message through the chat task, reporting failures to the client.

    Module-level rather than a closure over `run_chat_session`: it captured
    only that function's own three parameters, and nesting it summed its seven
    branches into the caller's mccabe score (22 against radon's 15), which is
    what held the mccabe ratchet three points above real complexity.

    Every exception is re-raised after broadcasting — the caller distinguishes
    cancel from timeout from failure, and only needs the client already told.
    """
    try:
        async with asyncio.timeout(timeout):
            await llm_chat_task.async_run(session=session_obj)
    except asyncio.CancelledError:
        raise
    except asyncio.TimeoutError:
        await session_manager.broadcast(session_id, "[TIMEOUT] LLM request timed out")
        raise
    except Exception:
        error_details = traceback.format_exc()
        await session_manager.broadcast(session_id, f"[ERROR] {error_details}")
        raise


def _snapshot_task_config(llm_chat_task: Any) -> dict[str, Any]:
    """Capture the shared task's mutable wiring so it can be restored after a run."""
    return {
        "ui_factories": list(llm_chat_task.ui_factories),
        "approval_channels": list(llm_chat_task.approval_channels),
        "history_manager": llm_chat_task.history_manager,
        "include_default_ui": llm_chat_task.include_default_ui,
    }


def _apply_session_config(
    llm_chat_task: Any,
    history_manager: Any,
    ui_factory: Any,
    approval_channel: Any,
) -> None:
    """Point the shared task at this session's UI factory / approval channel / history."""
    llm_chat_task.history_manager = history_manager
    llm_chat_task.ui_factories = [ui_factory]
    llm_chat_task.approval_channels = [approval_channel]
    llm_chat_task.include_default_ui = False


def _apply_task_config(llm_chat_task: Any, config: dict[str, Any]) -> None:
    """Restore a snapshot produced by `_snapshot_task_config`."""
    llm_chat_task.ui_factories = config["ui_factories"]
    llm_chat_task.approval_channels = config["approval_channels"]
    llm_chat_task.history_manager = config["history_manager"]
    llm_chat_task.include_default_ui = config["include_default_ui"]
