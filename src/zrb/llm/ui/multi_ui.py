import asyncio
import sys
from datetime import datetime
from typing import Any, TextIO

from zrb.util.cli.markdown import render_markdown
from zrb.util.cli.style import stylize_faint


class MultiUI:
    """UI wrapper that broadcasts output to multiple UIs and waits for first response.

    This class implements UIProtocol and delegates to multiple child UIs:
    - Output is broadcast to ALL child UIs
    - Input waits for FIRST response from ANY child UI
    - All child UIs share a SINGLE message queue (shared state)
    - Main UI (first by default) runs the main event loop

    Architecture:
        When any child UI receives user input, it should call MultiUI._submit_user_message()
        which:
        1. Broadcasts the user message to ALL UIs
        2. Puts a job in the shared message queue
        3. The shared queue processes jobs sequentially

    Usage:
        multi_ui = MultiUI([terminal_ui, telegram_ui])
        # Child UIs should route _submit_user_message through multi_ui
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
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._process_messages_task: asyncio.Task | None = None
        self._running_llm_task: asyncio.Task | None = None
        self._is_thinking: bool = False
        self._last_result_data: str | None = None
        self._llm_task: Any = None
        self._approval_channel: Any = None  # For tool approvals
        self._last_winning_ui: Any = None  # Track winning UI for tool confirmations
        self._tool_call_handler: Any = None  # Handler with formatters/policies from default UI
        # Set parent reference on all child UIs so they route messages through MultiUI
        for ui in self._uis:
            ui._multi_ui_parent = self

    def set_tool_call_handler(self, handler: Any):
        """Set the tool call handler with formatters/policies.

        This should be set to the same handler used by the default UI,
        so CLI mode in MultiUI has the same formatters as standalone CLI.
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"[MultiUI] set_tool_call_handler called, formatters: {[f.__name__ for f in handler._argument_formatters]}")
        self._tool_call_handler = handler

    def set_approval_channel(self, channel: Any):
        """Set the approval channel for tool confirmations."""
        self._approval_channel = channel

    @property
    def _main_ui(self) -> Any:
        return self._uis[self._main_ui_index] if self._uis else None

    def set_llm_task(self, llm_task: Any):
        """Set the LLM task for shared processing."""
        self._llm_task = llm_task
        for ui in self._uis:
            if hasattr(ui, "_llm_task"):
                ui._llm_task = llm_task

    def append_to_output(
        self,
        *values,
        sep=" ",
        end="\n",
        file: TextIO | None = None,
        flush: bool = False,
        **kwargs,
    ):
        """Broadcast output to ALL child UIs."""
        for ui in self._uis:
            try:
                ui.append_to_output(
                    *values, sep=sep, end=end, file=file, flush=flush, **kwargs
                )
            except Exception:
                pass

    async def _stream_ai_response(
        self,
        llm_task: Any,
        user_message: str,
        attachments: list[Any] = [],
    ):
        """Stream AI response to all UIs via shared queue."""
        self._is_thinking = True
        self.invalidate_all_uis()
        try:
            timestamp = datetime.now().strftime("%H:%M")
            self.append_to_output(f"\n🤖 {timestamp} >>\n")
            self.append_to_output(stylize_faint("\n  🔢 Streaming response..."))

            session = self._create_session_for_llm_task(user_message, attachments)
            llm_task.set_ui(self)
            llm_task.tool_confirmation = self._confirm_tool_execution

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
            if result_data is not None:
                if isinstance(result_data, str):
                    self._last_result_data = result_data
                    self.append_to_output("\n")
                    self.append_to_output(render_markdown(result_data, width=None))

        except asyncio.CancelledError:
            self.append_to_output("\n[Cancelled]\n")
            raise
        except Exception as e:
            self.append_to_output(f"\n[Error: {e}]\n")
        finally:
            self._is_thinking = False
            self.invalidate_all_uis()

    def invalidate_all_uis(self):
        """Invalidate all child UIs."""
        for ui in self._uis:
            try:
                if hasattr(ui, "invalidate_ui"):
                    ui.invalidate_ui()
            except Exception:
                pass

    def _create_session_for_llm_task(
        self,
        user_message: str,
        attachments: list[Any],
    ) -> Any:
        """Create session for LLM task."""
        from zrb.context.shared_context import SharedContext
        from zrb.session.session import Session

        session_input = {
            "message": user_message,
            "session": getattr(self._uis[0], "_conversation_session_name", "default"),
            "yolo": getattr(self._uis[0], "_yolo", False),
            "attachments": attachments,
            "model": getattr(self._uis[0], "_model", None),
        }
        shared_ctx = SharedContext(
            input=session_input,
            print_fn=self.append_to_output,
            is_web_mode=True,
        )
        return Session(shared_ctx)

    async def _confirm_tool_execution(self, call: Any):
        """Handle tool execution confirmation.

        Priority:
        1. Use MultiUI's handler if available (has formatters from default UI)
        2. Fall back to winning UI's handler if available
        3. Fall back to approval channel (Telegram buttons)
        """
        import logging
        import sys
        logger = logging.getLogger(__name__)

        # CRITICAL: Print at the very start to ensure we see this
        print(f"!!! MultiUI._confirm_tool_execution CALLED !!!", file=sys.stderr)
        print(f"    id(self)={id(self)}, type={type(self).__name__}", file=sys.stderr)
        print(f"    id(self._tool_call_handler)={id(self._tool_call_handler) if self._tool_call_handler else None}", file=sys.stderr)
        if self._tool_call_handler:
            print(f"    formatters={[f.__name__ for f in self._tool_call_handler._argument_formatters]}", file=sys.stderr)
        else:
            print(f"    _tool_call_handler is None!", file=sys.stderr)

        # First, try MultiUI's handler (has formatters from default UI)
        if self._tool_call_handler is not None:
            print(f"    -> Using MultiUI's _tool_call_handler", file=sys.stderr)
            return await self._tool_call_handler.handle(self, call)

        # Try winning UI's handler
        winning_ui = getattr(self, "_last_winning_ui", None)
        if winning_ui is not None and hasattr(winning_ui, "_tool_call_handler"):
            print(f"    -> Using winning_ui's _tool_call_handler", file=sys.stderr)
            return await winning_ui._tool_call_handler.handle(self, call)

        # Fall back to approval channel (e.g., Telegram buttons)
        if hasattr(self, "_approval_channel") and self._approval_channel is not None:
            from zrb.llm.approval.approval_channel import ApprovalContext

            print(f"    -> Falling back to approval channel", file=sys.stderr)
            context = ApprovalContext(
                tool_name=call.tool_name,
                tool_args=call.args if isinstance(call.args, dict) else {},
                tool_call_id=call.tool_call_id,
            )
            result = await self._approval_channel.request_approval(context)
            return result.to_pydantic_result()

        # Final fallback: use default handler from first UI
        if self._uis and hasattr(self._uis[0], "_tool_call_handler"):
            print(f"    -> Using first UI's _tool_call_handler", file=sys.stderr)
            return await self._uis[0]._tool_call_handler.handle(self, call)

        # Should not reach here, but raise for safety
        logger.error("[MultiUI] No handler found!")
        raise RuntimeError("No UI available for tool confirmation")

    def _submit_user_message(self, llm_task: Any, user_message: str):
        """Submit user message to shared queue.

        This is called by child UIs when they receive user input.
        Broadcasts to ALL UIs and puts job in shared queue.
        """
        timestamp = datetime.now().strftime("%H:%M")
        self.append_to_output(f"\n💬 {timestamp} >> {user_message.strip()}\n")

        async def job():
            await self._stream_ai_response(llm_task, user_message, [])

        self._message_queue.put_nowait(job)

    async def _process_messages_loop(self):
        """Process jobs from shared queue sequentially."""
        while True:
            try:
                job = await self._message_queue.get()

                while (
                    self._running_llm_task is not None
                    and not self._running_llm_task.done()
                ):
                    await asyncio.sleep(0.1)

                current_task = asyncio.current_task()
                if current_task:
                    task = asyncio.create_task(job())
                    self._running_llm_task = task

                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    finally:
                        self._running_llm_task = None

                self._message_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                import logging

                logging.getLogger(__name__).error(f"Error in message queue: {e}")
                await asyncio.sleep(1)

    async def ask_user(self, prompt: str) -> str:
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
                    task = loop.create_task(ui.ask_user(prompt))
                    pending_tasks[task] = (i, ui)
            except Exception:
                pass

        if not pending_tasks:
            return ""

        self._pending_input_tasks = list(pending_tasks.keys())
        winning_ui_index = None

        try:
            done, pending = await asyncio.wait(
                pending_tasks.keys(), return_when=asyncio.FIRST_COMPLETED
            )

            completed_task = done.pop()
            winning_ui_index, winning_ui = pending_tasks[completed_task]

            # Store winning UI for use in tool confirmations
            self._last_winning_ui = winning_ui

            for task in pending:
                task.cancel()

            try:
                result = completed_task.result()
                self._clear_pending_confirmations_except(winning_ui_index)
                return result
            except Exception:
                return ""
        finally:
            self._pending_input_tasks = []

    def _clear_pending_confirmations_except(self, except_index: int):
        """Cancel pending confirmation futures in all UIs except the winner.

        This prevents Terminal's confirmation queue from getting out of sync
        when another UI wins the input race.
        """
        for i, ui in enumerate(self._uis):
            if i == except_index:
                continue
            try:
                if hasattr(ui, "_cancel_pending_confirmations"):
                    ui._cancel_pending_confirmations()
            except Exception:
                pass

    def stream_to_parent(
        self,
        *values,
        sep=" ",
        end="\n",
        file: TextIO | None = None,
        flush: bool = False,
        **kwargs,
    ):
        for ui in self._uis:
            try:
                ui.stream_to_parent(
                    *values, sep=sep, end=end, file=file, flush=flush, **kwargs
                )
            except Exception:
                pass

    async def run_interactive_command(
        self, cmd: str | list[str], shell: bool = False
    ) -> Any:
        return await self._main_ui.run_interactive_command(cmd, shell=shell)

    async def _start_child_ui(self, ui: Any) -> None:
        """Start a child UI's event loop if it has one."""
        if hasattr(ui, "start_event_loop"):
            await ui.start_event_loop()
        elif hasattr(ui, "run_async") and ui is not self._main_ui:
            await ui.run_async()

    async def run_async(self) -> str:
        """Run all child UIs and the shared message loop."""
        if not self._main_ui:
            return ""

        self._shutdown_event = asyncio.Event()

        # Start shared message processor
        self._process_messages_task = asyncio.create_task(self._process_messages_loop())

        # Set LLM task on all UIs
        if hasattr(self._main_ui, "_llm_task"):
            self.set_llm_task(self._main_ui._llm_task)

        # Start all child UIs' event loops (except main UI)
        for i, ui in enumerate(self._uis):
            if i != self._main_ui_index:
                task = asyncio.create_task(self._start_child_ui(ui))
                self._child_tasks.append(task)

        # Run main UI's async loop
        main_task = asyncio.create_task(self._main_ui.run_async())

        try:
            await main_task
        except asyncio.CancelledError:
            main_task.cancel()
            await main_task
        except Exception:
            pass
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

        self.last_output = getattr(self._main_ui, "last_output", "")
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
            self._main_ui.on_exit()
        except Exception:
            pass


def is_shutdown_requested() -> bool:
    return getattr(sys, "_zrb_shutdown_requested", False)
