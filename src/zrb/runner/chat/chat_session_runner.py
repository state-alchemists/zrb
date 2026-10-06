"""Per-session chat loop: drains the SSE input queue, drives `LLMChatTask`.

All SSE sessions share one `LLMChatTask`. Per message, under
`ChatSessionManager.task_lock`, the task's UI/approval/history config is
pointed at this session, the message runs, and the prior config is restored.
"""

from __future__ import annotations

import asyncio
import traceback
from typing import Any

from zrb.config.config import CFG
from zrb.context.shared_context import SharedContext
from zrb.llm.tool.ambient_state import current_chat_session_id, input_provenance
from zrb.runner.chat.chat_session_manager import ChatSession, ChatSessionManager
from zrb.runner.chat.http_ui import create_http_ui_factory
from zrb.session.session import Session
from zrb.util.contextvar_scope import scoped
from zrb.util.exception import exception_summary


async def run_chat_session(
    session: ChatSession,
    llm_chat_task: Any,
    session_manager: ChatSessionManager,
) -> None:
    """Drive an SSE chat session through `llm_chat_task` until cancelled."""
    current_task = asyncio.current_task()
    assert current_task is not None

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
            queued = await _next_queued_message(session, current_task)
            if queued is None:
                continue

            message = queued["message"]
            session_manager.set_processing(session.session_id, True)
            CFG.LOGGER.info(f"Processing message: {message[:100]}")
            await session_manager.broadcast(session.session_id, f"[USER] {message}")
            session_obj = Session(
                shared_ctx=_build_message_context(
                    session.session_name, message, queued.get("attachments") or []
                )
            )
            try:
                with scoped(input_provenance, queued.get("source")):
                    await _run_one_message(
                        session,
                        session_obj,
                        llm_chat_task,
                        session_manager,
                        http_ui_factory,
                        approval_channel,
                    )
            except asyncio.CancelledError:
                session_manager.set_processing(session.session_id, False)
                raise
            except Exception as e:
                # Already broadcast; keep the loop alive for queued messages.
                CFG.LOGGER.error(f"LLM task error: {exception_summary(e)}")
            session_manager.set_processing(session.session_id, False)
    except asyncio.CancelledError:
        raise
    except Exception as e:
        error_msg = f"[ERROR] {str(e)}\n{traceback.format_exc()}\n"
        await session_manager.broadcast(session.session_id, error_msg)
    finally:
        session_manager.set_processing(session.session_id, False)


async def _next_queued_message(
    session: ChatSession, current_task: "asyncio.Task"
) -> dict | None:
    """The next queued message, or `None` when the poll timed out."""
    try:
        return await asyncio.wait_for(
            session.input_queue.get(),
            timeout=CFG.LLM_INPUT_QUEUE_TIMEOUT / 1000,
        )
    except asyncio.TimeoutError:
        if current_task.cancelling() > 0:
            # wait_for's timeout raced an external cancel() and swallowed it.
            raise asyncio.CancelledError()
        return None


def _build_message_context(
    session_name: str, message: str, attachments: list[str]
) -> SharedContext:
    """The `SharedContext` one queued message runs under."""
    return SharedContext(
        input={
            "message": message,
            "session": session_name,
            "yolo": "false",
            # Comma-joined, matching the CLI's `--attach` input.
            "attach": ",".join(attachments),
            "model": "",
            # Otherwise the CLI default (True in a terminal) runs the
            # interactive branch per message: history replay, SESSION_END hooks.
            "interactive": "false",
        }
    )


async def _run_one_message(
    session: ChatSession,
    session_obj: Any,
    llm_chat_task: Any,
    session_manager: ChatSessionManager,
    http_ui_factory: Any,
    approval_channel: Any,
) -> None:
    """Configure the shared task for this session, run one message, restore it."""
    llm_task: asyncio.Task | None = None
    async with session_manager.task_lock:
        saved = _snapshot_task_config(llm_chat_task)
        _apply_session_config(
            llm_chat_task,
            history_manager=session_manager.history_manager,
            ui_factory=http_ui_factory,
            approval_channel=approval_channel,
        )
        try:
            # create_task copies the context, so the run keeps this value.
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
            await _unwind_cancelled_task(llm_task)
            raise
        finally:
            _apply_task_config(llm_chat_task, saved)


async def _unwind_cancelled_task(llm_task: "asyncio.Task | None") -> None:
    """Cancel an in-flight run and wait for it to unwind before config is restored."""
    if llm_task is None or llm_task.done():
        return
    llm_task.cancel()
    try:
        await llm_task
    except asyncio.CancelledError:
        pass
    except Exception as unwind_error:
        CFG.LOGGER.warning(f"LLM task error during cancel-unwind: {unwind_error!r}")


async def _run_llm_message(
    session_obj: Any,
    timeout: float,
    llm_chat_task: Any,
    session_manager: ChatSessionManager,
    session_id: str,
) -> None:
    """Run one message through the chat task; broadcast failures, then re-raise."""
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
