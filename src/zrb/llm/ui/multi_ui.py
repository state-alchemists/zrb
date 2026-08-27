import asyncio
import inspect
import logging
import sys
from datetime import datetime
from typing import TYPE_CHECKING, Any, TextIO

if TYPE_CHECKING:
    from pydantic_ai.usage import RequestUsage, RunUsage

    from zrb.llm.tool_call.ui_protocol import ChoiceSpec

from zrb.config.config import CFG
from zrb.context.shared_context import SharedContext
from zrb.llm.approval.approval_channel import ApprovalContext
from zrb.llm.permission.state import (
    AgentMode,
    get_current_agent_mode,
    set_current_agent_mode,
)
from zrb.llm.ui.base.message_queue import (
    MessageQueue,
    QueuedMessage,
    steer_into_live_run,
)
from zrb.session.session import Session
from zrb.util.cli.markdown import render_markdown
from zrb.util.cli.style import stylize_muted

logger = logging.getLogger(__name__)


class MultiUI:
    """UI wrapper that broadcasts output to multiple UIs and waits for first response.

    This class implements UIProtocol and delegates to multiple child UIs:
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

    def __init__(self, uis: list[Any], main_ui_index: int = 0):
        self._uis = uis
        self._main_ui_index = main_ui_index
        self._responses: dict[int, asyncio.Future[str]] = {}
        self.last_output: str = ""
        self._shutdown_event: asyncio.Event | None = None
        self._child_tasks: list[asyncio.Task] = []
        self._pending_input_tasks: list[asyncio.Task] = []
        # Shared message queue for all UIs
        self._message_queue: MessageQueue = MessageQueue()
        self._active_run_context: Any = None
        self._process_messages_task: asyncio.Task | None = None
        self._running_llm_task: asyncio.Task | None = None
        self._is_thinking: bool = False
        self._last_result_data: str | None = None
        self._llm_task: Any = None
        self._approval_channel: Any = None  # For tool approvals
        self._last_winning_ui: Any = None  # Track winning UI for tool confirmations
        self._tool_call_handler: Any = (
            None  # Handler with formatters/policies from default UI
        )
        # Set parent reference on all child UIs so they route messages through MultiUI
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
        instead of queuing it (ADR-0078)."""
        return self._active_run_context

    @active_run_context.setter
    def active_run_context(self, ctx: Any) -> None:
        self._active_run_context = ctx

    def set_llm_task(self, llm_task: Any):
        """Set the LLM task for shared processing."""
        self._llm_task = llm_task
        for ui in self._uis:
            if hasattr(ui, "llm_task"):
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

    def accumulate_usage(
        self, usage: "RunUsage", context_usage: "RequestUsage | None" = None
    ) -> None:
        """Forward one run's usage totals to every child UI.

        Mirrors `append_to_output`: the agent runner wires its usage callback
        to the effective UI, which is a MultiUI in dual/multi-UI mode. Without
        forwarding, session token totals never accumulate on child UIs and the
        terminal status-bar meter stays empty.
        """
        for ui in self._uis:
            accumulate = getattr(ui, "accumulate_usage", None)
            if callable(accumulate):
                try:
                    accumulate(usage, context_usage)
                except Exception as e:
                    CFG.LOGGER.debug(f"Child UI accumulate_usage failed: {e}")

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
        for ui in self._uis:
            mark = getattr(ui, "mark_thinking_block_start", None)
            if callable(mark):
                try:
                    mark()
                except Exception as e:
                    CFG.LOGGER.debug(f"Child UI mark_thinking_block_start failed: {e}")

    def collapse_thinking_block(self, collapsed: str, full: str) -> None:
        """Counterpart to `mark_thinking_block_start` — see its docstring."""
        for ui in self._uis:
            collapse = getattr(ui, "collapse_thinking_block", None)
            if callable(collapse):
                try:
                    collapse(collapsed, full)
                except Exception as e:
                    CFG.LOGGER.debug(f"Child UI collapse_thinking_block failed: {e}")

    def replay_history(self, messages: list) -> None:
        """Replay loaded history on every child UI that supports it."""
        for ui in self._uis:
            replay = getattr(ui, "replay_history", None)
            if callable(replay):
                try:
                    replay(messages)
                except Exception as e:
                    CFG.LOGGER.debug(f"Child UI history replay failed: {e}")

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
            # Take filesystem snapshot before this AI turn (also records message
            # count so that a rewind can restore conversation history to a
            # consistent state). Failures are non-fatal — the AI turn must
            # proceed regardless. Mirrors BaseUI._stream_ai_response.
            snapshot_manager = getattr(self.main_ui, "snapshot_manager", None)
            if snapshot_manager is not None:
                try:
                    label = user_message[:80].replace("\n", " ").strip()
                    current_msgs = getattr(self.main_ui, "history_manager", None)
                    session_name = getattr(
                        self.main_ui, "conversation_session_name", ""
                    )
                    msgs = (
                        current_msgs.load(session_name)
                        if current_msgs is not None
                        else []
                    )
                    await snapshot_manager.take_snapshot(
                        f"{timestamp}: {label}", message_count=len(msgs)
                    )
                except Exception as snap_err:
                    logger.warning(f"Snapshot skipped: {snap_err}")
            self.append_to_output(f"\n🤖 {timestamp} >>\n")
            self.append_to_output(stylize_muted("\n  🔢 Streaming response..."))

            # Sync plan mode to the shared mutable state before the LLM run
            # so the agent inherits the mode set by /plan on the main UI.
            set_current_agent_mode(
                AgentMode.PLAN
                if getattr(self.main_ui, "plan_mode_active", False)
                else AgentMode.BUILD
            )

            session = self.create_session_for_llm_task(user_message, attachments)
            llm_task.set_ui(self)
            llm_task.tool_confirmation = self.confirm_tool_execution

            async def run_task():
                return await llm_task.async_run(session)

            task = asyncio.create_task(run_task())
            self._running_llm_task = task

            try:
                result_data = await task
            except asyncio.CancelledError:
                self.append_to_output("\n[Cancelled]\n")
                raise
            except Exception as e:
                self.append_to_output(f"\n[Error: {e}]\n")
                return

            self._running_llm_task = None

            # Sync plan mode after LLM response (tools like EnterPlanMode set
            # the ContextVar which is visible here in the same Task context), so
            # the main UI's /plan badge follows in-run mode changes.
            if hasattr(self.main_ui, "plan_mode_active"):
                self.main_ui.plan_mode_active = (
                    get_current_agent_mode() == AgentMode.PLAN
                )

            if result_data is not None:
                if isinstance(result_data, str):
                    self._last_result_data = result_data
                    self.append_to_output("\n")
                    # Render the final answer on the main UI with its themed,
                    # re-wrappable markdown path; other children keep the
                    # pre-rendered text they consumed before.
                    rendered = render_markdown(result_data, width=None)
                    for ui in self._uis:
                        try:
                            append_markdown = getattr(ui, "append_markdown", None)
                            if callable(append_markdown):
                                append_markdown(result_data)
                            else:
                                ui.append_to_output(rendered, end="")
                        except Exception as e:
                            CFG.LOGGER.debug(f"Child UI append failed: {e}")

        except asyncio.CancelledError:
            self.append_to_output("\n[Cancelled]\n")
            raise
        except Exception as e:
            self.append_to_output(f"\n[Error: {e}]\n")
        finally:
            # Stop the animation flag first, then refresh system/git info,
            # then repaint — mirrors BaseUI's finally order
            # (flag → update_system_info → invalidate) so the status bar
            # shows fresh values instead of a stale repaint.
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
            if hasattr(ui, "is_thinking"):
                ui.is_thinking = value
        if repaint:
            self.invalidate_all_uis()

    def invalidate_all_uis(self):
        """Invalidate all child UIs."""
        for ui in self._uis:
            try:
                if hasattr(ui, "invalidate_ui"):
                    ui.invalidate_ui()
            except Exception as e:
                # Best-effort repaint of each child UI.
                CFG.LOGGER.debug(f"Child UI invalidate_ui failed: {e}")

    def create_session_for_llm_task(
        self,
        user_message: str,
        attachments: list[Any],
    ) -> Any:
        """Create session for LLM task."""

        session_input = {
            "message": user_message,
            "session": getattr(self._uis[0], "conversation_session_name", "default"),
            "yolo": getattr(self._uis[0], "yolo", False),
            "attachments": attachments,
            "model": getattr(self._uis[0], "model", None),
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
        # First, try MultiUI's handler (has formatters from default UI)
        if self._tool_call_handler is not None:
            return await self._tool_call_handler.handle(self, call)

        winning_ui = self.last_winning_ui
        winning_handler = getattr(winning_ui, "tool_call_handler", None)
        if winning_handler is not None:
            return await winning_handler.handle(self, call)

        # Fall back to approval channel (e.g., Telegram buttons)
        if hasattr(self, "_approval_channel") and self._approval_channel is not None:

            context = ApprovalContext(
                tool_name=call.tool_name,
                tool_args=call.args if isinstance(call.args, dict) else {},
                tool_call_id=call.tool_call_id,
            )
            result = await self._approval_channel.request_approval(context)
            return result.to_pydantic_result()

        # Final fallback: use default handler from first UI
        if self._uis and hasattr(self._uis[0], "tool_call_handler"):
            return await self._uis[0].tool_call_handler.handle(self, call)

        raise RuntimeError("No UI available for tool confirmation")

    def submit_user_message(self, llm_task: Any, user_message: str):
        """Submit user message to shared queue.

        This is called by child UIs when they receive user input.
        Broadcasts to ALL UIs and puts job in shared queue.
        """
        timestamp = datetime.now().strftime("%H:%M")
        echo = f"\n💬 {timestamp} >> {user_message.strip()}\n"
        self.append_to_output(echo)

        # Collect pending attachments from all child UIs (e.g. images pasted
        # via Ctrl+V in the default terminal UI) and clear their queues.
        attachments = []
        for ui in self._uis:
            if hasattr(ui, "take_pending_attachments"):
                attachments.extend(ui.take_pending_attachments())

        if steer_into_live_run(self.active_run_context, user_message, attachments):
            return

        entry = QueuedMessage(
            text=user_message,
            attachments=attachments,
            kind="message",
            run=lambda: self.stream_ai_response(
                llm_task, entry.text, entry.attachments
            ),
        )
        entry.echo_marker = "💬"
        entry.echo_timestamp = timestamp
        # Record the echoed span on every child that can redraw in place so an
        # edit of this still-queued message rewrites the line everywhere.
        for ui in self._uis:
            track = getattr(ui, "_track_echo_span", None)
            if callable(track):
                track(entry, echo)

        self._message_queue.put_nowait(entry)

    def submit_message(self, user_message: str) -> None:
        """Queue *user_message* for the shared agent turn (steer into the live
        run when one is in flight, ADR-0078). Uses the shared queue's own task
        — sub-agent continuation code calls this to hand the main agent a
        synthesized report."""
        self.submit_user_message(self._llm_task, user_message)

    async def process_messages_loop(self):
        """Process jobs from shared queue sequentially."""
        while True:
            try:
                entry = await self._message_queue.get()

                # Wait for any still-running task from a previous iteration to
                # finish. Await it directly instead of polling — this removes
                # the busy-wait and the check-then-act race between done() and
                # the next assignment. Swallow its outcome (incl. cancellation);
                # this loop only needs it settled before starting the next job.
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
                        # Two different cancellations arrive here and they need
                        # opposite handling. A cancel aimed at THIS loop (the
                        # shutdown path in run_async/on_exit) must land, or the
                        # queue keeps running and `await self._process_messages_task`
                        # never returns. A cancel aimed only at the job — one
                        # response interrupted, session continuing — must not,
                        # or the loop exits and no further user message is ever
                        # processed. `cancelling()` tells them apart, the same
                        # guard base/ui.py's twin uses.
                        current = asyncio.current_task()
                        if current is not None and current.cancelling() > 0:
                            raise
                    finally:
                        self._running_llm_task = None

                self._message_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:

                logging.getLogger(__name__).error(f"Error in message queue: {e}")
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
        if is_shutdown_requested():
            return ""

        loop = asyncio.get_running_loop()
        pending_tasks: dict[asyncio.Task, tuple[int, Any]] = {}

        for i, ui in enumerate(self._uis):
            try:
                if hasattr(ui, "ask_user"):
                    task = loop.create_task(
                        ui.ask_user(
                            prompt, output_to_parent=output_to_parent, agent_id=agent_id
                        )
                    )
                    pending_tasks[task] = (i, ui)
            except Exception as e:
                CFG.LOGGER.debug(f"Child UI ask_user setup failed: {e}")

        if not pending_tasks:
            return ""

        self._pending_input_tasks = list(pending_tasks.keys())
        winning_ui_index = None

        try:
            done, pending = await asyncio.wait(
                pending_tasks.keys(), return_when=asyncio.FIRST_COMPLETED
            )

            # Several UIs may finish in the same wait round; pick the one
            # with the lowest UI index so the winner never depends on set
            # iteration order.
            completed_task = min(done, key=lambda t: pending_tasks[t][0])
            winning_ui_index, winning_ui = pending_tasks[completed_task]

            # Store winning UI for use in tool confirmations
            self._last_winning_ui = winning_ui

            for task in done:
                if task is not completed_task:
                    task.cancel()
            for task in pending:
                task.cancel()

            try:
                result = completed_task.result()
            except Exception as e:
                CFG.LOGGER.debug(f"Winning UI ask_user failed: {e}")
                # Still sync sibling confirmation queues: no input race is in
                # flight anymore, so stale confirmations must not linger.
                self.clear_pending_confirmations_except(winning_ui_index)
                return ""
            self.clear_pending_confirmations_except(winning_ui_index)
            return result
        finally:
            self._pending_input_tasks = []

    async def ask_user_choice(
        self, spec: "ChoiceSpec", agent_id: str | None = None
    ) -> str:
        """Race all UIs for a multiple-choice answer and return the first.

        Mirrors `ask_user`: the first UI to answer wins, the others are
        cancelled, and pending confirmations elsewhere are cleared to keep
        each UI's confirmation queue in sync.
        """
        if is_shutdown_requested():
            return ""

        loop = asyncio.get_running_loop()
        pending_tasks: dict[asyncio.Task, tuple[int, Any]] = {}

        for i, ui in enumerate(self._uis):
            try:
                if hasattr(ui, "ask_user_choice"):
                    task = loop.create_task(ui.ask_user_choice(spec, agent_id=agent_id))
                    pending_tasks[task] = (i, ui)
            except Exception as e:
                CFG.LOGGER.debug(f"Child UI ask_user_choice setup failed: {e}")

        if not pending_tasks:
            return ""

        self._pending_input_tasks = list(pending_tasks.keys())

        try:
            done, pending = await asyncio.wait(
                pending_tasks.keys(), return_when=asyncio.FIRST_COMPLETED
            )

            # Same deterministic winner rule as `ask_user`.
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
                CFG.LOGGER.debug(f"Winning UI ask_user_choice failed: {e}")
                self.clear_pending_confirmations_except(winning_ui_index)
                return ""
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
                if hasattr(ui, "cancel_pending_confirmations"):
                    ui.cancel_pending_confirmations()
            except Exception as e:
                # Best-effort cancel across child UIs during teardown.
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

    async def _start_child_ui(self, ui: Any) -> None:
        """Start a child UI's event loop if it has one."""
        if hasattr(ui, "start_event_loop"):
            await ui.start_event_loop()
        elif hasattr(ui, "run_async") and ui is not self.main_ui:
            await ui.run_async()

    async def run_async(self) -> str:
        """Run all child UIs and the shared message loop."""
        if not self.main_ui:
            return ""

        self._last_result_data = None

        self._shutdown_event = asyncio.Event()

        self._process_messages_task = asyncio.create_task(self.process_messages_loop())

        if hasattr(self.main_ui, "llm_task"):
            self.set_llm_task(self.main_ui.llm_task)

        for i, ui in enumerate(self._uis):
            if i != self._main_ui_index:
                task = asyncio.create_task(self._start_child_ui(ui))
                self._child_tasks.append(task)

        main_task = asyncio.create_task(self.main_ui.run_async())

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
            # Cancel all tasks
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
            else getattr(self.main_ui, "last_output", "")
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
            # Best-effort teardown of the main UI.
            CFG.LOGGER.debug(f"Main UI on_exit failed: {e}")


def is_shutdown_requested() -> bool:
    return getattr(sys, "zrb_shutdown_requested", False)
