import asyncio
import inspect
import logging
import sys
from collections.abc import Callable, Coroutine
from datetime import datetime
from typing import TYPE_CHECKING, Any, TextIO

if TYPE_CHECKING:
    from pydantic_ai.models import Model

    from zrb.llm.agent.types import RequestUsage, RunUsage
    from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
    from zrb.llm.snapshot.manager import SnapshotManager

    from zrb.llm.ui.any_ui import ChoiceSpec

from zrb.config.config import CFG
from zrb.context.shared_context import SharedContext
from zrb.llm.approval.any_approval_channel import ApprovalContext
from zrb.llm.hook.types import HookEvent
from zrb.llm.input_source import KEYBOARD_INPUT, InputProvenance
from zrb.llm.permission.state import (
    AgentMode,
    get_current_agent_mode,
    set_current_agent_mode,
)
from zrb.llm.ui.any_ui import AnyUI
from zrb.llm.ui.base.message_queue import MessageQueue, submit_user_message_via_queue
from zrb.llm.ui.state_defaults import UIStateDefaultsMixin
from zrb.llm.ui.turn_hooks import get_turn_hook_manager
from zrb.llm.ui.turn_snapshot import take_pre_turn_snapshot
from zrb.session.session import Session
from zrb.util.cli.markdown import render_markdown
from zrb.util.cli.style import stylize_muted
from zrb.util.exception import exception_summary

logger = logging.getLogger(__name__)


class MultiUI(UIStateDefaultsMixin, AnyUI):
    """UI wrapper that broadcasts output to multiple UIs and waits for first response.

    Output goes to every child; input takes the first child's answer; all
    children share one message queue; the main UI runs the main event loop.
    Child UIs route `submit_user_message` through this wrapper.

    Usage:
        multi_ui = MultiUI([terminal_ui, telegram_ui])
        # Child UIs should route submit_user_message through multi_ui
        llm_task.set_ui(multi_ui)
    """

    def __init__(self, uis: list[AnyUI], main_ui_index: int = 0):
        self._uis = uis
        self._main_ui_index = main_ui_index
        self._responses: dict[int, asyncio.Future[str]] = {}
        self._last_output: str = ""
        self._shutdown_event: asyncio.Event | None = None
        self._child_tasks: list[asyncio.Task] = []
        self._pending_input_tasks: list[asyncio.Task] = []
        self._message_queue: MessageQueue = MessageQueue()
        self._active_run_context: Any = None
        self._process_messages_task: asyncio.Task | None = None
        self._running_llm_task: asyncio.Task | None = None
        self._is_thinking: bool = False
        self._last_result_data: str | None = None
        self._llm_task: Any = None
        self._approval_channel: Any = None
        self._last_winning_ui: Any = None
        self._tool_call_handler: Any = None
        for ui in self._uis:
            ui.multi_ui_parent = self

    def set_tool_call_handler(self, handler: Any):
        """Set the tool call handler (normally the default UI's own)."""
        self._tool_call_handler = handler

    @property
    def tool_call_handler(self) -> Any:
        """Get the tool call handler."""
        return self._tool_call_handler

    @property
    def last_winning_ui(self) -> Any:
        """The child UI whose input won the last confirmation race, if any."""
        return self._last_winning_ui

    @last_winning_ui.setter
    def last_winning_ui(self, value: Any) -> None:
        self._last_winning_ui = value

    @property
    def child_tasks(self) -> list[asyncio.Task]:
        """Background tasks spawned per-child (e.g. trigger loops)."""
        return self._child_tasks

    @child_tasks.setter
    def child_tasks(self, value: list[asyncio.Task]) -> None:
        self._child_tasks = value

    @property
    def pending_input_tasks(self) -> list[asyncio.Task]:
        """In-flight `ask_user`/`ask_user_choice` races across child UIs."""
        return self._pending_input_tasks

    @pending_input_tasks.setter
    def pending_input_tasks(self, value: list[asyncio.Task]) -> None:
        self._pending_input_tasks = value

    @property
    def process_messages_task(self) -> "asyncio.Task | None":
        """The background task running `process_messages_loop`, if started."""
        return self._process_messages_task

    @process_messages_task.setter
    def process_messages_task(self, value: "asyncio.Task | None") -> None:
        self._process_messages_task = value

    def set_approval_channel(self, channel: Any):
        """Set the approval channel for tool confirmations."""
        self._approval_channel = channel

    @property
    def children(self) -> list[Any]:
        """The wrapped child UIs."""
        return list(self._uis)

    @property
    def main_ui(self) -> Any:
        return self._uis[self._main_ui_index] if self._uis else None

    @property
    def last_output(self) -> str:
        """The last answer rendered through this MultiUI."""
        return self._last_output

    @last_output.setter
    def last_output(self, value: str) -> None:
        self._last_output = value

    # State the main child owns, read and written there.
    @property
    def model(self) -> "str | Model | None":
        return self.main_ui.model if self.main_ui is not None else None

    @model.setter
    def model(self, value: "str | Model | None") -> None:
        if self.main_ui is not None:
            self.main_ui.model = value

    @property
    def small_model(self) -> "str | Model | None":
        return self.main_ui.small_model if self.main_ui is not None else None

    @small_model.setter
    def small_model(self, value: "str | Model | None") -> None:
        if self.main_ui is not None:
            self.main_ui.small_model = value

    @property
    def multimodal_model(self) -> "str | Model | None":
        return self.main_ui.multimodal_model if self.main_ui is not None else None

    @multimodal_model.setter
    def multimodal_model(self, value: "str | Model | None") -> None:
        if self.main_ui is not None:
            self.main_ui.multimodal_model = value

    @property
    def conversation_session_name(self) -> str:
        return (
            self.main_ui.conversation_session_name if self.main_ui is not None else ""
        )

    @conversation_session_name.setter
    def conversation_session_name(self, value: str) -> None:
        if self.main_ui is not None:
            self.main_ui.conversation_session_name = value

    @property
    def plan_mode_active(self) -> bool:
        return self.main_ui.plan_mode_active if self.main_ui is not None else False

    @plan_mode_active.setter
    def plan_mode_active(self, value: bool) -> None:
        if self.main_ui is not None:
            self.main_ui.plan_mode_active = value

    @property
    def yolo(self) -> bool | frozenset:
        return self.main_ui.yolo if self.main_ui is not None else False

    @property
    def snapshot_manager(self) -> "SnapshotManager | None":
        return self.main_ui.snapshot_manager if self.main_ui is not None else None

    @property
    def history_manager(self) -> "AnyHistoryManager | None":
        return self.main_ui.history_manager if self.main_ui is not None else None

    @property
    def llm_task(self) -> Any:
        return self._llm_task

    @llm_task.setter
    def llm_task(self, value: Any) -> None:
        self.set_llm_task(value)

    @property
    def message_queue(self) -> "MessageQueue":
        """The shared queue every child UI's turn is submitted through."""
        return self._message_queue

    @property
    def is_thinking(self) -> bool:
        """Whether a turn is currently streaming through this MultiUI."""
        return self._is_thinking

    @is_thinking.setter
    def is_thinking(self, value: bool) -> None:
        self._is_thinking = value

    @property
    def last_result_data(self) -> "str | None":
        """The raw last-turn result, or None before any turn has completed."""
        return self._last_result_data

    @last_result_data.setter
    def last_result_data(self, value: "str | None") -> None:
        self._last_result_data = value

    @property
    def active_run_context(self) -> Any:
        """The live `RunContext` of the streaming turn, or None; lets
        `submit_user_message` steer into it."""
        return self._active_run_context

    @active_run_context.setter
    def active_run_context(self, ctx: Any) -> None:
        self._active_run_context = ctx

    def set_llm_task(self, llm_task: Any):
        """Set the LLM task for shared processing."""
        self._llm_task = llm_task
        for ui in self._uis:
            ui.llm_task = llm_task

    def append_to_output(
        self,
        *values,
        sep=" ",
        end="\n",
        file: TextIO | None = None,
        flush: bool = False,
        kind: str = "text",
    ):
        """Broadcast output to ALL child UIs."""
        for ui in self._uis:
            try:
                ui.append_to_output(
                    *values, sep=sep, end=end, file=file, flush=flush, kind=kind
                )
            except Exception as e:
                CFG.LOGGER.debug(f"Child UI append_to_output failed: {e}")

    def set_status_badge(self, key: str, text: str | None) -> None:
        self._fanout("set_status_badge", key, text)

    def _fanout(self, method_name: str, /, *args, **kwargs) -> None:
        """Call `method_name` on every child that implements it, best-effort:
        a dead channel is not a dead run."""
        for ui in self._uis:
            fn = getattr(ui, method_name, None)
            if not callable(fn):
                continue
            try:
                fn(*args, **kwargs)
            except Exception as e:
                CFG.LOGGER.debug(f"Child UI {method_name} failed: {e}")

    def accumulate_usage(
        self, usage: "RunUsage", context_usage: "RequestUsage | None" = None
    ) -> None:
        """Forward one run's usage totals to every child UI."""
        self._fanout("accumulate_usage", usage, context_usage)

    def append_markdown(self, markdown_text: str) -> None:
        """Render `markdown_text` on every child.

        Children with their own `append_markdown` get the source; others get
        pre-rendered output.
        """
        rendered = render_markdown(markdown_text, width=None)
        for ui in self._uis:
            try:
                child_append = getattr(ui, "append_markdown", None)
                if callable(child_append):
                    child_append(markdown_text)
                else:
                    ui.append_to_output(rendered, end="")
            except Exception as e:
                CFG.LOGGER.debug(f"Child UI append failed: {e}")

    def record_tool_call_block(self, collapsed: str, full: str) -> None:
        """Give every child its tool-call/result line.

        Children without `record_tool_call_block` get a plain
        `append_to_output`: the caller sends the line through only one of the
        two, so every child must be reached here.
        """
        for ui in self._uis:
            record = getattr(ui, "record_tool_call_block", None)
            if callable(record):
                try:
                    record(collapsed, full)
                    continue
                except Exception as e:
                    CFG.LOGGER.debug(f"Child UI record_tool_call_block failed: {e}")
            try:
                ui.append_to_output(collapsed, end="", kind="tool_call")
            except Exception as e:
                CFG.LOGGER.debug(f"Child UI append_to_output failed: {e}")

    def mark_thinking_block_start(self) -> None:
        """Mark a live thinking block's start on toggle-capable children.

        No fallback needed: the text itself reaches every child through
        `append_to_output`.
        """
        self._fanout("mark_thinking_block_start")

    def collapse_thinking_block(self, collapsed: str, full: str) -> None:
        """Collapse the block opened by `mark_thinking_block_start`."""
        self._fanout("collapse_thinking_block", collapsed, full)

    def mark_text_block_start(self) -> None:
        """Mark the final-text reply block's start on toggle-capable children."""
        self._fanout("mark_text_block_start")

    def collapse_text_block(self, collapsed: str, full: str) -> None:
        """Collapse the block opened by `mark_text_block_start`."""
        self._fanout("collapse_text_block", collapsed, full)

    def start_tool_call(self, tool_name: str, tool_call_id: str) -> None:
        """Forward a tool call's start to children tracking the running-tool timer."""
        self._fanout("start_tool_call", tool_name, tool_call_id)

    def end_tool_call(self, tool_call_id: str | None = None) -> None:
        """Forward a tool call's end to children tracking the running-tool timer."""
        self._fanout("end_tool_call", tool_call_id)

    def update_tool_prepare(self, key: str, text: str) -> None:
        """Forward a "Prepare tool parameters" update to children that support it."""
        self._fanout("update_tool_prepare", key, text)

    def update_shell_output(self, key: str, text: str) -> None:
        """Forward a live shell-output update to children that support it."""
        self._fanout("update_shell_output", key, text)

    def finish_shell_output(self, key: str, collapsed: str, full: str) -> None:
        """Collapse `key`'s live shell-output line on children that support it."""
        self._fanout("finish_shell_output", key, collapsed, full)

    def replay_history(self, messages: list) -> None:
        """Replay loaded history on every child UI that supports it."""
        self._fanout("replay_history", messages)

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
                self.append_markdown(result_data)

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
                update_info = getattr(ui, "update_system_info", None)
                if inspect.iscoroutinefunction(update_info):
                    try:
                        await update_info()
                    except Exception as e:
                        CFG.LOGGER.debug(f"Child UI system info update failed: {e}")
            self.invalidate_ui()

    def set_thinking(self, value: bool, repaint: bool = True) -> None:
        """Mirror the thinking flag to every child UI, then repaint.

        Children's status bars read their own `is_thinking`. `repaint=False`
        lets callers refresh system info first.
        """
        self._is_thinking = value
        for ui in self._uis:
            ui.is_thinking = value
        if repaint:
            self.invalidate_ui()

    def invalidate_ui(self) -> None:
        """Ask every child UI to repaint."""
        for ui in self._uis:
            try:
                ui.invalidate_ui()
            except Exception as e:
                CFG.LOGGER.debug(f"Child UI invalidate_ui failed: {e}")

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
            "yolo": main_ui.yolo,
            "attachments": attachments,
            "model": main_ui.model,
        }
        shared_ctx = SharedContext(
            input=session_input,
            print_fn=self.append_to_output,
            is_web_mode=True,
        )
        return Session(shared_ctx)

    async def confirm_tool_execution(self, call: Any):
        """Handle tool execution confirmation.

        Priority:
        1. Use MultiUI's handler if available (has formatters from default UI)
        2. Fall back to winning UI's handler if available
        3. Fall back to approval channel (Telegram buttons)
        """
        if self._tool_call_handler is not None:
            return await self._tool_call_handler.handle(self, call)

        winning_ui = self.last_winning_ui
        winning_handler = getattr(winning_ui, "tool_call_handler", None)
        if winning_handler is not None:
            return await winning_handler.handle(self, call)

        if self._approval_channel is not None:
            context = ApprovalContext(
                tool_name=call.tool_name,
                tool_args=call.args if isinstance(call.args, dict) else {},
                tool_call_id=call.tool_call_id,
            )
            result = await self._approval_channel.request_approval(context)
            return result.to_pydantic_result()

        # Final fallback: the primary child's own handler.
        main_ui = self.main_ui
        if main_ui is not None and main_ui.tool_call_handler is not None:
            return await main_ui.tool_call_handler.handle(self, call)

        raise RuntimeError(
            "MultiUI has no attached UI and no approval channel that can "
            "confirm this tool call — construct it with at least one UI, or "
            "call set_approval_channel(...) before running."
        )

    def submit_user_message(
        self,
        llm_task: Any,
        user_message: str,
        source: InputProvenance | None = KEYBOARD_INPUT,
    ):
        """Broadcast a child's user input to every UI and queue the turn.

        Attachments and echoes fan out to every child. The message is recorded
        once, on the primary child, since all children share one history file.
        """
        main_ui = self.main_ui
        recorder = getattr(main_ui, "record_submitted_message", None)
        if recorder is not None:
            recorder(user_message)
        submit_user_message_via_queue(
            append_to_output=self.append_to_output,
            active_run_context=self.active_run_context,
            stream_ai_response=self.stream_ai_response,
            queue=self._message_queue,
            attachment_sources=self._uis,
            echo_targets=self._uis,
            llm_task=llm_task,
            user_message=user_message,
            marker="💬",
            append_markdown=self.append_markdown,
            source=source,
        )

    def submit_message(
        self,
        user_message: str,
        source: InputProvenance | None = None,
    ) -> None:
        """Queue *user_message* for the shared agent turn, or steer it into
        the live run."""
        self.submit_user_message(self._llm_task, user_message, source)

    async def process_messages_loop(self):
        """Process jobs from shared queue sequentially."""
        while True:
            try:
                entry = await self._message_queue.get()

                # Settle a still-running previous job, swallowing its outcome
                # unless the cancel is aimed at this loop.
                if (
                    self._running_llm_task is not None
                    and not self._running_llm_task.done()
                ):
                    try:
                        await self._running_llm_task
                    except (KeyboardInterrupt, SystemExit):
                        raise
                    except BaseException:
                        current = asyncio.current_task()
                        if current is not None and current.cancelling() > 0:
                            raise

                current_task = asyncio.current_task()
                if current_task:
                    task = asyncio.create_task(entry.run())
                    self._running_llm_task = task

                    try:
                        await task
                    except asyncio.CancelledError:
                        # Re-raise only a cancel aimed at this loop, not the job.
                        current = asyncio.current_task()
                        if current is not None and current.cancelling() > 0:
                            raise
                    finally:
                        self._running_llm_task = None

                self._message_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in message queue: {e}")
                await asyncio.sleep(CFG.LLM_UI_STATUS_INTERVAL / 1000)

    async def ask_user(
        self,
        prompt: str,
        output_to_parent: str = "",
        agent_id: str | None = None,
    ) -> str:
        """Race all UIs for input and return the first response.

        The losers' prompts are cancelled once one UI answers.
        """
        return await self._race_children(
            lambda ui: ui.ask_user(
                prompt, output_to_parent=output_to_parent, agent_id=agent_id
            ),
            "ask_user",
        )

    async def ask_user_choice(
        self, spec: "ChoiceSpec", agent_id: str | None = None
    ) -> str:
        """Race all UIs for a multiple-choice answer and return the first,
        with the same rules as `ask_user`."""
        return await self._race_children(
            lambda ui: ui.ask_user_choice(spec, agent_id=agent_id), "ask_user_choice"
        )

    async def _race_children(
        self, ask: Callable[[Any], Coroutine[Any, Any, str]], label: str
    ) -> str:
        """Return the first answer any child gives.

        A failed child drops out rather than winning: an empty answer approves
        a tool call. With no child left to answer this raises, as
        `MultiplexApprovalChannel` denies.
        """
        if is_shutdown_requested():
            raise RuntimeError(f"Shutdown requested; {label} has no answer")
        loop = asyncio.get_running_loop()
        pending_tasks: dict[asyncio.Task, tuple[int, Any]] = {}
        for i, ui in enumerate(self._uis):
            try:
                pending_tasks[loop.create_task(ask(ui))] = (i, ui)
            except Exception as e:
                CFG.LOGGER.debug(f"Child UI {label} setup failed: {e}")
        if not pending_tasks:
            raise RuntimeError(f"No child UI could take {label}")
        # Shared by concurrent races; each removes only its own tasks.
        self._pending_input_tasks.extend(pending_tasks)
        waiting: set[asyncio.Task] = set(pending_tasks)
        last_error: BaseException | None = None
        try:
            while waiting:
                done, waiting = await asyncio.wait(
                    waiting, return_when=asyncio.FIRST_COMPLETED
                )
                # Several UIs may finish in the same wait round; the lowest
                # index wins so the result never depends on set iteration order.
                for task in sorted(done, key=lambda t: pending_tasks[t][0]):
                    if task.cancelled():
                        continue
                    error = task.exception()
                    if error is not None:
                        CFG.LOGGER.debug(f"Child UI {label} failed: {error}")
                        last_error = error
                        continue
                    self._last_winning_ui = pending_tasks[task][1]
                    return task.result()
            raise RuntimeError(f"Every child UI failed {label}") from last_error
        finally:
            # Cancelling a loser releases that loser's prompt and no other.
            for task in pending_tasks:
                task.cancel()
            await asyncio.gather(*pending_tasks, return_exceptions=True)
            for task in pending_tasks:
                if task in self._pending_input_tasks:
                    self._pending_input_tasks.remove(task)

    @property
    def is_turn_running(self) -> bool:
        """Whether this MultiUI is running a turn (its children run none)."""
        running = self._running_llm_task
        return running is not None and not running.done()

    def cancel_pending_confirmations(self, flush: bool = True) -> None:
        """Release every child's pending confirmation."""
        for ui in self._uis:
            ui.cancel_pending_confirmations(flush)

    def cancel_current_turn(self, reason: str) -> None:
        """Release children's confirmations, cancel this MultiUI's turn and
        fire `Stop` with *reason* once."""
        self.cancel_pending_confirmations()
        running = self._running_llm_task
        if running is None or running.done():
            return
        running.cancel()
        main_ui = self.main_ui
        stop = get_turn_hook_manager(self._llm_task).execute_hooks(
            HookEvent.STOP,
            {
                "reason": reason,
                "session": main_ui.conversation_session_name if main_ui else "",
            },
        )
        task = asyncio.get_running_loop().create_task(stop)
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)

    @property
    def is_waiting_for_answer(self) -> bool:
        """Whether any child holds a prompt waiting for the user."""
        return any(ui.is_waiting_for_answer for ui in self._uis)

    def is_prompt_answered_since(self, asked_at: float) -> bool:
        """Whether any child has answered the first prompt asked at or after
        *asked_at*: an answer from any of them settles it."""
        return any(ui.is_prompt_answered_since(asked_at) for ui in self._uis)

    def stream_to_parent(
        self,
        *values,
        sep=" ",
        end="\n",
        file: TextIO | None = None,
        flush: bool = False,
        kind: str = "text",
    ):
        for ui in self._uis:
            try:
                ui.stream_to_parent(
                    *values, sep=sep, end=end, file=file, flush=flush, kind=kind
                )
            except Exception as e:
                CFG.LOGGER.debug(f"Child UI stream_to_parent failed: {e}")

    async def run_interactive_command(
        self, cmd: str | list[str], shell: bool = False
    ) -> Any:
        return await self.main_ui.run_interactive_command(cmd, shell=shell)

    async def _start_child_ui(self, ui: AnyUI) -> None:
        """Start a child UI's event loop if it has one."""
        # `start_event_loop` is EventDrivenUI-only, hence the probe.
        start_event_loop: Any = getattr(ui, "start_event_loop", None)
        if start_event_loop is not None:
            await start_event_loop()
        elif ui is not self.main_ui:
            await ui.run_async()

    async def run_async(self) -> str:
        """Run all child UIs and the shared message loop."""
        main_ui = self.main_ui
        if main_ui is None:
            return ""

        self._last_result_data = None

        self._shutdown_event = asyncio.Event()

        self._process_messages_task = asyncio.create_task(self.process_messages_loop())

        self.set_llm_task(main_ui.llm_task)

        for i, ui in enumerate(self._uis):
            if i != self._main_ui_index:
                task = asyncio.create_task(self._start_child_ui(ui))
                self._child_tasks.append(task)

        main_task = asyncio.create_task(main_ui.run_async())

        try:
            await main_task
        except asyncio.CancelledError:
            main_task.cancel()
            # A teardown error must not mask the cancellation.
            try:
                await main_task
            except asyncio.CancelledError:
                pass
            except Exception as unwind_error:
                CFG.LOGGER.warning(
                    f"Main UI error during cancel-unwind: {unwind_error!r}"
                )
            raise
        except Exception as e:
            CFG.LOGGER.debug(f"Main UI task ended with error: {e}")
        finally:
            if self._process_messages_task:
                self._process_messages_task.cancel()
                try:
                    await self._process_messages_task
                except asyncio.CancelledError:
                    pass

            for task in self._child_tasks:
                task.cancel()
            await asyncio.gather(*self._child_tasks, return_exceptions=True)
            self._child_tasks = []

            for task in self._pending_input_tasks:
                if not task.done():
                    task.cancel()
            self._pending_input_tasks = []

        self.last_output = (
            self._last_result_data
            if self._last_result_data is not None
            else (self.main_ui.last_output if self.main_ui is not None else "")
        )
        return self.last_output

    def on_exit(self):
        if self._shutdown_event:
            self._shutdown_event.set()
        for task in self._child_tasks:
            task.cancel()
        for task in self._pending_input_tasks:
            task.cancel()
        if self._process_messages_task:
            self._process_messages_task.cancel()
        try:
            self.main_ui.on_exit()
        except Exception as e:
            CFG.LOGGER.debug(f"Main UI on_exit failed: {e}")


def is_shutdown_requested() -> bool:
    return getattr(sys, "zrb_shutdown_requested", False)


def create_combined_ui(uis: "AnyUI | list[AnyUI]", fallback: "AnyUI") -> "AnyUI":
    """One UI for *uis*: itself, its only member, a `MultiUI`, or *fallback*
    when the list is empty."""
    if not isinstance(uis, list):
        return uis
    if not uis:
        return fallback
    return uis[0] if len(uis) == 1 else MultiUI(uis)
