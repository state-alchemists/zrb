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
from zrb.runner.chat.chat_session_manager import ChatSession, ChatSessionManager
from zrb.runner.chat.http_ui import create_http_ui_factory
from zrb.session.session import Session


async def run_chat_session(
    session: ChatSession,
    llm_chat_task: Any,
    session_manager: ChatSessionManager,
) -> None:
    """Drive an SSE chat session through `llm_chat_task` until cancelled."""
    current_task = asyncio.current_task()

    async def run_llm_message(session_obj: Any, timeout: float) -> None:
        try:
            async with asyncio.timeout(timeout):
                await llm_chat_task.async_run(session=session_obj)
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            await session_manager.broadcast(
                session.session_id, "[TIMEOUT] LLM request timed out"
            )
            raise
        except Exception:
            error_details = traceback.format_exc()
            await session_manager.broadcast(
                session.session_id, f"[ERROR] {error_details}"
            )
            raise

    # The per-session UI factory / approval channel are independent objects — safe
    # to build once. The shared LLMChatTask is configured + driven under
    # `session_manager.task_lock` per message (see _drive_shared_task) so concurrent
    # sessions never clobber each other's wiring mid-run.
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
                message = await asyncio.wait_for(
                    session.input_queue.get(),
                    timeout=CFG.LLM_INPUT_QUEUE_TIMEOUT / 1000,
                )
            except asyncio.CancelledError:
                if llm_task and not llm_task.done():
                    llm_task.cancel()
                raise
            except asyncio.TimeoutError:
                if current_task.cancelling() > 0:
                    if llm_task and not llm_task.done():
                        llm_task.cancel()
                    raise
                continue

            session_manager.set_processing(session.session_id, True)
            CFG.LOGGER.info(f"Processing message: {message[:100]}")
            await session_manager.broadcast(session.session_id, f"[USER] {message}")

            shared_ctx = SharedContext(
                input={
                    "message": message,
                    "session": session.session_name,
                    "yolo": "false",
                    "attachments": "",
                    "model": "",
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
                        llm_task = asyncio.create_task(
                            run_llm_message(session_obj, CFG.LLM_REQUEST_TIMEOUT / 1000)
                        )
                        await llm_task
                        CFG.LOGGER.info("LLM task completed")
                    finally:
                        _apply_task_config(llm_chat_task, saved)
            except asyncio.CancelledError:
                session_manager.set_processing(session.session_id, False)
                raise
            except Exception as e:
                CFG.LOGGER.error(f"LLM task error: {e}")
                raise
            session_manager.set_processing(session.session_id, False)
    except asyncio.CancelledError:
        raise
    except Exception as e:
        error_msg = f"[ERROR] {str(e)}\n{traceback.format_exc()}\n"
        await session_manager.broadcast(session.session_id, error_msg)
    finally:
        session_manager.set_processing(session.session_id, False)


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
