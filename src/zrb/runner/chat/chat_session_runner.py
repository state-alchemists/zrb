"""Per-session chat loop: drains the SSE input queue, drives `LLMChatTask`.

Swaps the chat task's UI factory and approval-channel list to the HTTP-
specific ones for the duration of the session and restores them on exit.
The privately-named attributes accessed here (`_ui_factories`,
`_approval_channels`, `_history_manager`, `_include_default_ui`) are an
acknowledged coupling — see AGENTS.md cross-cutting notes.
"""

from __future__ import annotations

import asyncio
from typing import Any

from zrb.config.config import CFG
from zrb.runner.chat.chat_session_manager import ChatSession, ChatSessionManager
from zrb.runner.chat.http_ui import create_http_ui_factory


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
            import traceback as tb_lib

            error_details = tb_lib.format_exc()
            await session_manager.broadcast(
                session.session_id, f"[ERROR] {error_details}"
            )
            raise

    try:
        from zrb.context.shared_context import SharedContext
        from zrb.session.session import Session

        # Snapshot the LLMChatTask configuration so we can restore it on exit;
        # multiple chat sessions share one LLMChatTask instance.
        saved_ui_factories = list(llm_chat_task._ui_factories)
        saved_approval_channels = list(llm_chat_task._approval_channels)
        saved_history_manager = llm_chat_task._history_manager
        saved_include_default_ui = llm_chat_task._include_default_ui

        try:
            llm_chat_task.set_history_manager(session_manager._history_manager)

            approval_channel = session.approval_channel
            http_ui_factory = create_http_ui_factory(
                session_manager,
                session.session_id,
                session.session_name,
                approval_channel,
            )
            llm_chat_task._ui_factories = [http_ui_factory]
            llm_chat_task._approval_channels = [approval_channel]
            llm_chat_task._include_default_ui = False

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
                llm_task = asyncio.create_task(
                    run_llm_message(session_obj, CFG.LLM_REQUEST_TIMEOUT / 1000)
                )
                try:
                    await llm_task
                    CFG.LOGGER.info("LLM task completed")
                except asyncio.CancelledError:
                    session_manager.set_processing(session.session_id, False)
                    raise
                except Exception as e:
                    CFG.LOGGER.error(f"LLM task error: {e}")
                    raise
                session_manager.set_processing(session.session_id, False)
        finally:
            llm_chat_task._ui_factories = saved_ui_factories
            llm_chat_task._approval_channels = saved_approval_channels
            llm_chat_task._history_manager = saved_history_manager
            llm_chat_task._include_default_ui = saved_include_default_ui
    except asyncio.CancelledError:
        raise
    except Exception as e:
        import traceback

        error_msg = f"[ERROR] {str(e)}\n{traceback.format_exc()}"
        await session_manager.broadcast(session.session_id, error_msg)
    finally:
        session_manager.set_processing(session.session_id, False)
