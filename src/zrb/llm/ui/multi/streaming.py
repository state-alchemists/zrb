"""One turn, streamed to every child.

The wrapper builds the session the turn runs in, hands the task to the shared
message loop, mirrors the thinking flag and the plan-mode badge, and settles
the answer on every child — so a chat with a terminal and a Telegram window
shows one turn, not two.
"""

import asyncio
from datetime import datetime
from typing import Any

from zrb.config.config import CFG
from zrb.context.shared_context import SharedContext
from zrb.llm.permission.state import (
    AgentMode,
    get_current_agent_mode,
    set_current_agent_mode,
)
from zrb.llm.ui.turn_snapshot import take_pre_turn_snapshot
from zrb.llm.util.spoken import shown_text
from zrb.session.session import Session
from zrb.util.cli.style import stylize_muted
from zrb.util.exception import exception_summary

from zrb.llm.ui.multi.tools import MultiUIToolForwards


class MultiUIStreaming(MultiUIToolForwards):
    """Run one turn, and show it on every child."""

    async def _take_pre_turn_snapshot(self, user_message: str, timestamp: str) -> None:
        main_ui = self.main_ui
        if main_ui is None or main_ui.snapshot_manager is None:
            return
        await take_pre_turn_snapshot(
            main_ui.snapshot_manager,
            main_ui.history_manager,
            main_ui.conversation_session_name,
            user_message,
            timestamp,
        )

    def create_session_for_llm_task(
        self,
        user_message: str,
        attachments: list[Any],
    ) -> Any:
        """Create a session whose name, approval mode and model come from the
        primary child (`main_ui_index`)."""
        main_ui = self.main_ui
        if main_ui is None:
            raise RuntimeError(
                "MultiUI has no attached UI to take the session name, approval "
                "mode and model from — construct it with at least one UI."
            )
        session_input = {
            "message": user_message,
            "session": main_ui.conversation_session_name or "default",
            "yolo": main_ui.tools.yolo,
            "attachments": attachments,
            "model": main_ui.model,
        }
        shared_ctx = SharedContext(
            input=session_input,
            print_fn=self.append_to_output,
            is_web_mode=True,
        )
        return Session(shared_ctx)

    async def stream_ai_response(
        self,
        llm_task: Any,
        user_message: str,
        attachments: list[Any] | None = None,
    ):
        """Stream AI response to all UIs via shared queue."""
        attachments = list(attachments or [])
        # A fresh turn has no answer yet; a non-string result or an error must
        # not leave last_output carrying the previous turn's answer.
        self._last_result_data = None
        # Clear a stale running-tool timer left by a cancelled turn.
        self.end_tool_call()
        self.set_thinking(True)
        try:
            timestamp = datetime.now().strftime("%H:%M")
            await self._take_pre_turn_snapshot(user_message, timestamp)
            self.append_to_output(f"\n🤖 {timestamp} >>\n")
            self.append_to_output(stylize_muted("\n  🔢 Streaming response..."))

            # The agent inherits the mode /plan set on the main UI.
            set_current_agent_mode(
                AgentMode.PLAN
                if self.main_ui is not None and self.main_ui.plan_mode_active
                else AgentMode.BUILD
            )

            session = self.create_session_for_llm_task(user_message, attachments)
            llm_task.set_ui(self)
            llm_task.tool_confirmation = self.confirm_tool_execution

            task = asyncio.create_task(llm_task.async_run(session))
            self._running_llm_task = task

            try:
                result_data = await task
            except asyncio.CancelledError:
                self.append_to_output("\n[Cancelled]\n")
                raise
            except Exception as e:
                self.append_to_output(f"\n[Error: {exception_summary(e)}]\n")
                return

            self._running_llm_task = None

            # Tools like EnterPlanMode change the mode in-run; keep the badge in step.
            if self.main_ui is not None:
                self.main_ui.plan_mode_active = (
                    get_current_agent_mode() == AgentMode.PLAN
                )

            if isinstance(result_data, str):
                self._last_result_data = result_data
                self.append_to_output("\n")
                # The answer keeps its `<spoken>` markers for speech; every
                # child shows the whole reply without them, in the run's column.
                self.append_answer(shown_text(result_data))
            if self.main_ui is not None:
                self.main_ui.conversation.schedule_auto_name(user_message)

        except asyncio.CancelledError:
            self.append_to_output("\n[Cancelled]\n")
            raise
        except Exception as e:
            self.append_to_output(f"\n[Error: {exception_summary(e)}]\n")
        finally:
            # Flag, then system info, then repaint, so the status bar never
            # repaints stale values.
            self.set_thinking(False, repaint=False)
            for ui in self._uis:
                try:
                    await ui.session.update_system_info()
                except Exception as e:
                    CFG.LOGGER.debug(f"Child UI system info update failed: {e}")
            self.invalidate_ui()
