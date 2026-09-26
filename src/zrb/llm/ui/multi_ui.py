import asyncio
import inspect
import logging
import sys
from collections.abc import Callable, Coroutine
from datetime import datetime
from typing import TYPE_CHECKING, Any, TextIO

if TYPE_CHECKING:
    from zrb.llm.agent.types import RequestUsage, RunUsage

    from zrb.llm.ui.any_ui import ChoiceSpec

from zrb.config.config import CFG
from zrb.context.shared_context import SharedContext
from zrb.llm.approval.any_approval_channel import ApprovalContext
from zrb.llm.permission.state import (
    AgentMode,
    get_current_agent_mode,
    set_current_agent_mode,
)
from zrb.llm.ui.any_ui import AnyUI
from zrb.llm.ui.base.message_queue import MessageQueue, submit_user_message_via_queue
from zrb.llm.ui.state_defaults import UIStateDefaultsMixin
from zrb.llm.ui.turn_snapshot import take_pre_turn_snapshot
from zrb.session.session import Session
from zrb.util.cli.markdown import render_markdown
from zrb.util.cli.style import stylize_muted
from zrb.util.exception import exception_summary

logger = logging.getLogger(__name__)


class MultiUI(UIStateDefaultsMixin, AnyUI):
    """UI wrapper that broadcasts output to multiple UIs and waits for first response.

    This class implements AnyUI and delegates to multiple child UIs:
    - Output is broadcast to ALL child UIs
    - Input waits for FIRST response from ANY child UI
    - All child UIs share a SINGLE message queue (shared state)
    - Main UI (first by default) runs the main event loop

    Architecture:
        When any child UI receives user input, it should call MultiUI.submit_user_message()
        which:
        1. Broadcasts the user message to ALL UIs
        2. Puts a job in the shared message queue
        3. The shared queue processes jobs sequentially

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
        """Set the tool call handler with formatters/policies.

        This should be set to the same handler used by the default UI,
        so CLI mode in MultiUI has the same formatters as standalone CLI.
        """
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
        """Public view of the wrapped child UIs.

        Lets collaborators (e.g. the agent runner) pick a concrete child UI
        without reaching into the private `_uis` list.
        """
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

    @property
    def small_model(self):
        """The main child's `/model small ...` override (delegated so the agent
        runner's `run_agent` binds `current_small_model` from the MultiUI itself
        rather than seeing `None` and falling back to CFG)."""
        return self.main_ui.small_model if self.main_ui is not None else None

    @small_model.setter
    def small_model(self, value: Any) -> None:
        """Write through to the main child, so a `/model small ...` applied to
        the MultiUI lands where `small_model` is read back from."""
        if self.main_ui is not None:
            self.main_ui.small_model = value

    @property
    def multimodal_model(self):
        """The main child's `/model multimodal ...` override — same delegation
        rationale as `small_model`."""
        return self.main_ui.multimodal_model if self.main_ui is not None else None

    @multimodal_model.setter
    def multimodal_model(self, value: Any) -> None:
        """Write through to the main child — same rationale as `small_model`."""
        if self.main_ui is not None:
            self.main_ui.multimodal_model = value

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
        """Mirrors `BaseUI.active_run_context` — the live pydantic-ai
        `RunContext` for the turn currently streaming through this MultiUI, or
        None between turns / while a turn is suspended. Read by
        `submit_user_message` to steer a new message into the live turn
        instead of queuing it."""
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

    def _fanout(self, method_name: str, /, *args, **kwargs) -> None:
        """Call `method_name` on every child that implements it.

        Children are best-effort: one child raising must not stop the others,
        because a MultiUI fans one agent run out to independent channels (TUI,
        SSE, Telegram) and a dead channel is not a dead run.
        """
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
        """Forward one run's usage totals to every child UI.

        Mirrors `append_to_output`: the agent runner wires its usage callback
        to the effective UI, which is a MultiUI in dual/multi-UI mode. Without
        forwarding, session token totals never accumulate on child UIs and the
        terminal status-bar meter stays empty.
        """
        self._fanout("accumulate_usage", usage, context_usage)

    def append_markdown(self, markdown_text: str) -> None:
        """Render `markdown_text` on every child that supports it.

        Children with their own `append_markdown` (the default TUI's themed,
        re-wrappable markdown path) get the source text; children without one
        (e.g. Telegram) get the pre-rendered output. Best-effort like
        `append_to_output`: one dead child channel must not kill the fan-out.
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

        Tracks it as a toggle span on whichever children support that (the
        default TUI, via their own `record_tool_call_block`), and falls back
        to a plain `append_to_output` for children that don't (Telegram,
        SSE) — so those channels keep receiving the line exactly as they did
        before expand/collapse existed. `StreamEventHandler` calls either
        this method or `append_to_output` for a given line, never both, so
        every child must be reached from right here.
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
        """Let whichever children support toggling record where a live
        thinking block begins.

        Unlike `record_tool_call_block`, no fallback is needed here: the
        thinking text itself already reached every child via the normal
        `append_to_output` broadcast (StreamEventHandler never withholds
        it) — this only lets toggle-capable children prepare to collapse
        it later. A child that doesn't support it just keeps showing that
        thinking text uncollapsed, which is a harmless default.
        """
        self._fanout("mark_thinking_block_start")

    def collapse_thinking_block(self, collapsed: str, full: str) -> None:
        """Counterpart to `mark_thinking_block_start` — see its docstring."""
        self._fanout("collapse_thinking_block", collapsed, full)

    def mark_text_block_start(self) -> None:
        """Counterpart to `mark_thinking_block_start` for the assistant's
        final-text reply instead of its reasoning — same fallback story."""
        self._fanout("mark_text_block_start")

    def collapse_text_block(self, collapsed: str, full: str) -> None:
        """Counterpart to `mark_text_block_start` — see its docstring."""
        self._fanout("collapse_text_block", collapsed, full)

    def update_tool_prepare(self, key: str, text: str) -> None:
        """Forward a tool call's "Prepare tool parameters" update to whichever
        children support it — same fallback story as `mark_thinking_block_start`."""
        self._fanout("update_tool_prepare", key, text)

    def update_shell_output(self, key: str, text: str) -> None:
        """Forward to whichever children support it — same fallback story
        as `update_tool_prepare`."""
        self._fanout("update_shell_output", key, text)

    def finish_shell_output(self, key: str, collapsed: str, full: str) -> None:
        """Counterpart to `update_shell_output` — see its docstring."""
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
        self.set_thinking(True)
        try:
            timestamp = datetime.now().strftime("%H:%M")
            await self._take_pre_turn_snapshot(user_message, timestamp)
            self.append_to_output(f"\n🤖 {timestamp} >>\n")
            self.append_to_output(stylize_muted("\n  🔢 Streaming response..."))

            # Sync plan mode to the shared mutable state before the LLM run
            # so the agent inherits the mode set by /plan on the main UI.
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

            # Sync plan mode after LLM response (tools like EnterPlanMode set
            # the ContextVar which is visible here in the same Task context), so
            # the main UI's /plan badge follows in-run mode changes.
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
            self.invalidate_all_uis()

    def set_thinking(self, value: bool, repaint: bool = True) -> None:
        """Mirror the thinking flag to every child UI, then repaint.

        The status-bar animation ("⏳ working…") and the fast refresh loop
        read each UI's own `is_thinking`, so the flag must live on the
        children, not only on the MultiUI wrapper. `repaint=False` defers the
        repaint so callers can refresh system info first.
        """
        self._is_thinking = value
        for ui in self._uis:
            ui.is_thinking = value
        if repaint:
            self.invalidate_all_uis()

    def invalidate_all_uis(self):
        """Invalidate all child UIs."""
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
        """Create session for LLM task.

        The run's session name, approval mode and model come from the *primary*
        child -- the one `main_ui_index` names and whose event loop drives the
        session -- not from `_uis[0]`, which is only the same child at the
        default index.
        """
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

    def submit_user_message(self, llm_task: Any, user_message: str):
        """Submit user message to shared queue.

        This is called by child UIs when they receive user input.
        Broadcasts to ALL UIs and puts job in shared queue. Attachments and
        the echo-span redraw fan out to every child (`self._uis`) — `MultiUI`
        holds no attachments or echo buffer of its own, unlike a standalone
        `BaseUI`, which submits on behalf of itself alone.
        """
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
        )

    def submit_message(self, user_message: str) -> None:
        """Queue *user_message* for the shared agent turn (steer into the live
        run when one is in flight). Uses the shared queue's own task
        — sub-agent continuation code calls this to hand the main agent a
        synthesized report."""
        self.submit_user_message(self._llm_task, user_message)

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
                        # A cancel aimed at this loop (shutdown) must land;
                        # one aimed only at the job must not stop the loop.
                        # `cancelling()` tells them apart.
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

        When one UI wins, cancel and clear pending confirmations in other UIs.
        This ensures Terminal's confirmation queue doesn't get out of sync.
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
        with the same cancel-and-clear rules as `ask_user`."""
        return await self._race_children(
            lambda ui: ui.ask_user_choice(spec, agent_id=agent_id), "ask_user_choice"
        )

    async def _race_children(
        self, ask: Callable[[Any], Coroutine[Any, Any, str]], label: str
    ) -> str:
        if is_shutdown_requested():
            return ""
        loop = asyncio.get_running_loop()
        pending_tasks: dict[asyncio.Task, tuple[int, Any]] = {}
        for i, ui in enumerate(self._uis):
            try:
                pending_tasks[loop.create_task(ask(ui))] = (i, ui)
            except Exception as e:
                CFG.LOGGER.debug(f"Child UI {label} setup failed: {e}")
        if not pending_tasks:
            return ""
        self._pending_input_tasks = list(pending_tasks.keys())
        try:
            done, pending = await asyncio.wait(
                pending_tasks.keys(), return_when=asyncio.FIRST_COMPLETED
            )
            # Several UIs may finish in the same wait round; the lowest index
            # wins so the result never depends on set iteration order.
            completed_task = min(done, key=lambda t: pending_tasks[t][0])
            winning_ui_index, winning_ui = pending_tasks[completed_task]
            self._last_winning_ui = winning_ui
            for task in done:
                if task is not completed_task:
                    task.cancel()
            for task in pending:
                task.cancel()
            try:
                result = completed_task.result()
            except Exception as e:
                CFG.LOGGER.debug(f"Winning UI {label} failed: {e}")
                result = ""
            # Sync sibling confirmation queues even on failure: no input race
            # is in flight anymore, so stale confirmations must not linger.
            self.clear_pending_confirmations_except(winning_ui_index)
            return result
        finally:
            self._pending_input_tasks = []

    def clear_pending_confirmations_except(self, except_index: int):
        """Cancel pending confirmation futures in all UIs except the winner.

        This prevents Terminal's confirmation queue from getting out of sync
        when another UI wins the input race.
        """
        for i, ui in enumerate(self._uis):
            if i == except_index:
                continue
            try:
                ui.cancel_pending_confirmations()
            except Exception as e:
                CFG.LOGGER.debug(f"Child UI cancel_pending_confirmations failed: {e}")

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
        # `start_event_loop` is EventDrivenUI's alone, so it stays a capability
        # probe. `run_async` is on the AnyUI contract, so it needs no probe.
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
            # Guard the unwind: an error raised while the main UI tears down
            # would propagate from here and mask the cancellation, so callers
            # would see an ordinary failure instead of a cancelled run.
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
