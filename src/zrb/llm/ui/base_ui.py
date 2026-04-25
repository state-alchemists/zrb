import asyncio
import inspect
import logging
import os
from collections.abc import AsyncIterable, Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any, TextIO

from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.context.shared_context import SharedContext
from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.hook.manager import hook_manager
from zrb.llm.hook.types import HookEvent
from zrb.llm.task.llm_task import LLMTask
from zrb.llm.tool_call import (
    ArgumentFormatter,
    ResponseHandler,
    ToolCallHandler,
    ToolPolicy,
    default_response_handler,
)
from zrb.llm.ui._commands_mixin import BaseUICommandsMixin
from zrb.session.any_session import AnySession
from zrb.session.session import Session
from zrb.task.any_task import AnyTask
from zrb.util.cli.markdown import render_markdown
from zrb.util.cli.style import stylize_error, stylize_faint
from zrb.util.string.name import get_random_name
from zrb.xcom.xcom import Xcom

if TYPE_CHECKING:
    from pydantic_ai import ToolApproved, ToolCallPart, ToolDenied, UserContent
    from pydantic_ai.models import Model
    from rich.theme import Theme

logger = logging.getLogger(__name__)


class BaseUI(BaseUICommandsMixin):
    """Base class for LLM Chat UI implementations.

    This class provides the core chat functionality (message handling, command
    processing, AI interaction) while delegating UI-specific rendering to subclasses.

    Architecture:
        BaseUI is designed to be subclassed for different UI backends:
        - Terminal UI (prompt_toolkit)
        - Telegram UI (python-telegram-bot)
        - Web UI (WebSocket/HTTP)
        - Simple UI (basic stdin/stdout)

    Required Methods (must be implemented by subclasses):
        - append_to_output(): Render output to user
        - ask_user(): Block and wait for user input
        - run_interactive_command(): Execute interactive shell commands
        - run_async(): Run the UI event loop

    Optional Methods (can be overridden):
        - invalidate_ui(): Refresh UI state
        - on_exit(): Clean exit handler
        - stream_to_parent(): Stream output to parent (for multiplexed UIs)
        - _get_output_field_width(): Custom output width

    Extension Levels:
        ┌─────────────────────────────────────────────────────────────────┐
        │ Level 0: UIProtocol (minimal, 4 methods)                        │
        │         - For tool confirmations only                           │
        ├─────────────────────────────────────────────────────────────────┤
        │ Level 1: BaseUI (base class for full implementations)           │
        │         - Implement 4 required methods + run_async()            │
        │         - For custom backends (Telegram, Discord, WebSocket)    │
        ├─────────────────────────────────────────────────────────────────┤
        │ Level 2: UI (terminal implementation)                           │
        │         - Full TUI with prompt_toolkit                          │
        ├─────────────────────────────────────────────────────────────────┤
        │ Level 3: MultiplexerUI (multi-channel support)                  │
        │         - Manages multiple child UIs                            │
        └─────────────────────────────────────────────────────────────────┘

    Example:
        Minimal custom UI::

            class MyUI(BaseUI):
                def append_to_output(self, *values, sep=" ", end="\\n", kind="text", **kwargs):
                    text = sep.join(str(v) for v in values) + end
                    print(text, end="")

                async def ask_user(self, prompt: str) -> str:
                    if prompt:
                        print(prompt, end="", flush=True)
                    return await asyncio.to_thread(input)

                async def run_interactive_command(self, cmd, shell=False):
                    proc = await asyncio.create_subprocess_shell(cmd)
                    await proc.wait()

                async def run_async(self):
                    # Start message processing loop
                    self._process_messages_task = asyncio.create_task(
                        self._process_messages_loop()
                    )
                    # Send initial message if provided
                    if self._initial_message:
                        self._submit_user_message(self._llm_task, self._initial_message)
                    # Keep running until cancelled
                    try:
                        while True:
                            await asyncio.sleep(CFG.LLM_UI_STATUS_INTERVAL / 1000)
                    except asyncio.CancelledError:
                        pass
                    finally:
                        self._process_messages_task.cancel()
    """

    def __init__(
        self,
        ctx: AnyContext,
        yolo_xcom_key: str,
        assistant_name: str,
        llm_task: LLMTask,
        history_manager: AnyHistoryManager,
        initial_message: Any = "",
        initial_attachments: list["UserContent"] = [],
        conversation_session_name: str = "",
        is_yolo: bool | frozenset = False,
        triggers: list[Callable[[], AsyncIterable[Any]]] = [],
        response_handlers: list[ResponseHandler] = [],
        tool_policies: list[ToolPolicy] = [],
        argument_formatters: list[ArgumentFormatter] = [],
        markdown_theme: "Theme | None" = None,
        summarize_commands: list[str] = [],
        attach_commands: list[str] = [],
        exit_commands: list[str] = [],
        info_commands: list[str] = [],
        save_commands: list[str] = [],
        load_commands: list[str] = [],
        rewind_commands: list[str] = [],
        redirect_output_commands: list[str] = [],
        yolo_toggle_commands: list[str] = [],
        set_model_commands: list[str] = [],
        exec_commands: list[str] = [],
        btw_commands: list[str] = [],
        custom_commands: list[AnyCustomCommand] = [],
        model: "Model | str | None" = None,
        enable_rewind: bool = False,
        snapshot_dir: str = "",
    ):
        self._ctx = ctx
        self._yolo_xcom_key = yolo_xcom_key
        self._is_thinking = False
        self._running_llm_task: asyncio.Task | None = None
        self._llm_task = llm_task
        self._history_manager = history_manager
        self._assistant_name = assistant_name
        self._initial_message = initial_message
        self._conversation_session_name = conversation_session_name
        if not self._conversation_session_name:
            self._conversation_session_name = get_random_name()
        self._model = model
        self._triggers = triggers
        self._markdown_theme = markdown_theme
        self._summarize_commands = summarize_commands
        self._attach_commands = attach_commands
        self._exit_commands = exit_commands
        self._info_commands = info_commands
        self._save_commands = save_commands
        self._load_commands = load_commands
        self._rewind_commands = rewind_commands
        self._redirect_output_commands = redirect_output_commands
        self._yolo_toggle_commands = yolo_toggle_commands
        self._set_model_commands = set_model_commands
        self._exec_commands = exec_commands
        self._btw_commands = btw_commands
        self._custom_commands = custom_commands
        self._trigger_tasks: list[asyncio.Task] = []
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._process_messages_task: asyncio.Task | None = None
        self._last_result_data: str | None = None

        # System Info
        self._cwd = os.getcwd()
        self._git_info = "Checking..."
        self._system_info_task: asyncio.Task | None = None

        # Snapshot / rewind
        self._snapshot_manager = None
        if enable_rewind and snapshot_dir and self._conversation_session_name:
            from zrb.llm.snapshot.manager import SnapshotManager

            self._snapshot_manager = SnapshotManager(
                snapshot_dir=snapshot_dir,
                session_name=self._conversation_session_name,
                workdir=self._cwd,
            )

        # Attachments
        self._pending_attachments: list["UserContent"] = list(initial_attachments)

        # Confirmation Handler
        self._tool_call_handler = ToolCallHandler(
            tool_policies=tool_policies,
            argument_formatters=argument_formatters,
            response_handlers=response_handlers + [default_response_handler],
        )
        # Queue for pending confirmation requests to handle parallel tool approvals
        self._confirmation_queue: list[tuple[asyncio.Future[str], str]] = []
        self._current_confirmation: asyncio.Future[str] | None = None

        # Track background tasks to prevent garbage collection
        self._background_tasks: set[asyncio.Task] = set()

        # Initialize yolo from parameter
        if is_yolo:
            self.yolo = is_yolo

    @property
    def tool_call_handler(self) -> Any:
        """Get the tool call handler for this UI."""
        return self._tool_call_handler

    @property
    def llm_task(self) -> Any:
        """Get the LLM task."""
        return self._llm_task

    @llm_task.setter
    def llm_task(self, value: Any):
        """Set the LLM task."""
        self._llm_task = value

    def execute_hook(self, event: HookEvent, event_data: Any, **kwargs) -> None:
        """
        Safely execute hooks from either sync or async context.
        Maintains strong references to tasks to prevent garbage collection.
        """
        try:
            # Try to get the running event loop
            loop = asyncio.get_running_loop()
            # We're in an async context with a running loop
            task = loop.create_task(
                hook_manager.execute_hooks(event, event_data, **kwargs)
            )

            # Keep a strong reference to prevent GC from destroying it mid-execution
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

        except RuntimeError:
            # No running event loop - we're in a sync context
            # Create a new event loop and run synchronously
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    hook_manager.execute_hooks(event, event_data, **kwargs)
                )
            finally:
                loop.close()

    @property
    def yolo(self) -> bool | frozenset:
        if self._yolo_xcom_key not in self._ctx.xcom:
            return False
        return self._ctx.xcom[self._yolo_xcom_key].get(False)

    @yolo.setter
    def yolo(self, value: bool | frozenset):
        if self._yolo_xcom_key not in self._ctx.xcom:
            self._ctx.xcom[self._yolo_xcom_key] = Xcom()
        self._ctx.xcom[self._yolo_xcom_key].set(value)

    @property
    def model(self) -> Any:
        """Get the current model."""
        return self._model

    @model.setter
    def model(self, value: Any):
        """Set the model."""
        self._model = value

    @property
    def conversation_session_name(self) -> str:
        """Get the conversation session name."""
        return self._conversation_session_name

    @conversation_session_name.setter
    def conversation_session_name(self, value: str):
        """Set the conversation session name."""
        self._conversation_session_name = value

    @property
    def triggers(self) -> list[Callable[[], AsyncIterable[Any]]]:
        return self._triggers

    @triggers.setter
    def triggers(self, value: list[Callable[[], AsyncIterable[Any]]]):
        self._triggers = value

    @property
    def last_output(self) -> str:
        if self._last_result_data is None:
            return ""
        return self._last_result_data

    @property
    def assistant_name(self) -> str:
        """Get the assistant name."""
        return self._assistant_name

    @property
    def initial_message(self) -> Any:
        """Get the initial message."""
        return self._initial_message

    @property
    def exit_commands(self) -> list[str]:
        """Get the list of exit commands."""
        return self._exit_commands

    @property
    def info_commands(self) -> list[str]:
        """Get the list of info/help commands."""
        return self._info_commands

    @property
    def save_commands(self) -> list[str]:
        """Get the list of save commands."""
        return self._save_commands

    @property
    def load_commands(self) -> list[str]:
        """Get the list of load commands."""
        return self._load_commands

    @property
    def attach_commands(self) -> list[str]:
        """Get the list of attach commands."""
        return self._attach_commands

    @property
    def redirect_output_commands(self) -> list[str]:
        """Get the list of redirect output commands."""
        return self._redirect_output_commands

    @property
    def yolo_toggle_commands(self) -> list[str]:
        """Get the list of yolo toggle commands."""
        return self._yolo_toggle_commands

    @property
    def set_model_commands(self) -> list[str]:
        """Get the list of set model commands."""
        return self._set_model_commands

    @property
    def exec_commands(self) -> list[str]:
        """Get the list of exec commands."""
        return self._exec_commands

    @property
    def custom_commands(self) -> list[AnyCustomCommand]:
        """Get the list of custom commands."""
        return self._custom_commands

    @property
    def summarize_commands(self) -> list[str]:
        """Get the list of summarize commands."""
        return self._summarize_commands

    # =========================================================================
    # REQUIRED METHODS - Must be implemented by subclasses
    # =========================================================================

    def append_to_output(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
        kind: str = "text",
    ):
        """[REQUIRED] Render output to the user.

        This method must be implemented by all UI subclasses to display
        AI responses, system messages, and other output to the user.

        Args:
            *values: Objects to display (converted to string via str())
            sep: Separator between values (default: space)
            end: String appended after all values (default: newline)
            file: Ignored (for print() compatibility)
            flush: Ignored (for print() compatibility)
            kind: Output kind — "text", "progress", "tool_call", "usage", or
                  "thinking". Use this to apply visual distinction (e.g. faint
                  styling for non-"text" kinds in terminal, CSS classes in web).

        Example:
            def append_to_output(self, *values, sep=" ", end="\\n", kind="text", **kwargs):
                text = sep.join(str(v) for v in values) + end
                if kind != "text":
                    text = stylize_faint(text)
                print(text, end="")
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement append_to_output()"
        )

    async def ask_user(self, prompt: str) -> str:
        """[REQUIRED] Block and wait for user input.

        This method must be implemented by all UI subclasses to receive
        user input. It should display the prompt (if provided) and block
        until the user provides input.

        Args:
            prompt: Optional prompt to display before waiting for input.
                   May be empty string if no prompt is needed.

        Returns:
            The user's input as a string.

        Example:
            async def ask_user(self, prompt: str) -> str:
                if prompt:
                    print(prompt, end="", flush=True)
                return await asyncio.to_thread(input)
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement ask_user()"
        )

    async def run_interactive_command(
        self, cmd: str | list[str], shell: bool = False
    ) -> Any:
        """[REQUIRED] Execute an interactive shell command.

        This method must be implemented by UI subclasses that support
        running shell commands from within the chat (e.g., via /exec command).
        For UIs that don't support this, raise NotImplementedError or return None.

        Args:
            cmd: Command to execute (string or list of arguments)
            shell: If True, run through shell (supports pipes, etc.)

        Returns:
            Command result (implementation-dependent)

        Example:
            async def run_interactive_command(self, cmd, shell=False):
                proc = await asyncio.create_subprocess_shell(cmd, shell=shell)
                await proc.wait()
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement run_interactive_command()"
        )

    async def run_async(self) -> str:
        """[REQUIRED] Run the UI event loop.

        This method must be implemented by all UI subclasses. It should:
        1. Start the message processing loop (via _process_messages_loop)
        2. Submit initial message if provided (_initial_message)
        3. Start any trigger loops if configured
        4. Run until the UI is closed or cancelled
        5. Return the last output

        Returns:
            The last output from the conversation (or empty string).

        Example:
            async def run_async(self):
                # Start background tasks
                self._process_messages_task = asyncio.create_task(
                    self._process_messages_loop()
                )
                # Send initial message if provided
                if self._initial_message:
                    self._submit_user_message(self._llm_task, self._initial_message)
                # Run until cancelled or stopped
                try:
                    while self._running:
                        await asyncio.sleep(0.1)
                except asyncio.CancelledError:
                    pass
                finally:
                    self._process_messages_task.cancel()
                return self.last_output
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement run_async()"
        )

    # =========================================================================
    # OPTIONAL METHODS - Can be overridden by subclasses
    # =========================================================================

    def stream_to_parent(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
        kind: str = "text",
    ):
        """[OPTIONAL] Stream output immediately to parent UI.

        For main UIs, this is typically the same as append_to_output().
        For child UIs in a multiplexer setup, this streams to the parent UI
        instead of buffering locally.

        Override this method if your UI needs to distinguish between
        local output and output that should be immediately forwarded.

        Args:
            *values: Objects to stream
            sep: Separator between values
            end: String appended after all values
            file: Ignored
            flush: Ignored
            kind: Output kind — "text", "progress", "tool_call", "usage", or "thinking".
        """
        self.append_to_output(
            *values, sep=sep, end=end, file=file, flush=flush, kind=kind
        )

    def invalidate_ui(self):
        """[OPTIONAL] Refresh the UI state.

        Called when the UI needs to be redrawn or refreshed. Override this
        method if your UI backend requires explicit refresh calls (e.g.,
        terminal TUI frameworks, websockets).

        Default implementation does nothing.
        """
        pass

    def on_exit(self):
        """[OPTIONAL] Handle application exit.

        Called when the user requests to exit the application. Override
        this method to perform cleanup tasks (close connections, save state, etc.)

        Default implementation does nothing.
        """
        pass

    def _get_output_field_width(self) -> int | None:
        """[OPTIONAL] Get the width for text output formatting.

        Override this method to provide a custom width for markdown
        rendering and text wrapping. Return None for no width constraint.

        Returns:
            Width in characters, or None for no constraint.
        """
        return None

    async def _process_messages_loop(self):
        """Process jobs from queue, ensuring only one job runs at a time."""
        while True:
            try:
                job = await self._message_queue.get()

                # Wait if there is a running task (e.g. from previous iteration just finishing cleanup)
                while (
                    self._running_llm_task is not None
                    and not self._running_llm_task.done()
                ):
                    await asyncio.sleep(0.1)

                # Create task for current job
                current_task = asyncio.create_task(job())
                self._running_llm_task = current_task

                try:
                    await current_task
                except asyncio.CancelledError:
                    # Task was cancelled (e.g. via UI)
                    # Wait for task to fully complete its cancellation
                    try:
                        await current_task
                    except asyncio.CancelledError:
                        pass  # Task is now fully cancelled
                    # Continue to next job
                except Exception as e:
                    logger.error(f"Error executing job: {e}")
                finally:
                    self._running_llm_task = None

                self._message_queue.task_done()

            except asyncio.CancelledError:
                break
            except RuntimeError as e:
                # Event loop closed during shutdown - exit immediately
                logger.error(f"RuntimeError in message queue loop: {e}")
                break
            except Exception as e:
                logger.error(f"Error in message queue loop: {e}")
                # Don't break loop on error, but handle event loop closure
                try:
                    await asyncio.sleep(CFG.LLM_UI_STATUS_INTERVAL / 1000)
                except RuntimeError:
                    # Event loop closed - exit
                    break

    def _submit_user_message(self, llm_task: AnyTask, user_message: str):
        # Check if we have a parent MultiUI to route through
        parent_multi_ui = getattr(self, "_multi_ui_parent", None)
        if parent_multi_ui is not None:
            # Route through parent MultiUI - this broadcasts to ALL UIs
            parent_multi_ui._submit_user_message(llm_task, user_message)
            return

        # No parent - process locally (original behavior)
        timestamp = datetime.now().strftime("%H:%M")
        # 1. Render User Message
        self.append_to_output(f"\n💬 {timestamp} >> {user_message.strip()}\n")
        # 2. Trigger AI Response
        attachments = list(self._pending_attachments)
        self._pending_attachments.clear()

        async def job():
            await self._stream_ai_response(llm_task, user_message, attachments)

        self._message_queue.put_nowait(job)

    async def _stream_ai_response(
        self,
        llm_task: LLMTask,
        user_message: str,
        attachments: list["UserContent"] = [],
    ):
        self._is_thinking = True
        self.invalidate_ui()
        try:
            timestamp = datetime.now().strftime("%H:%M")
            # Take filesystem snapshot before this AI turn (also records message count
            # so that a rewind can restore conversation history to a consistent state).
            # Failures are non-fatal — the AI turn must proceed regardless.
            if self._snapshot_manager is not None:
                try:
                    label = user_message[:80].replace("\n", " ").strip()
                    current_msgs = self._history_manager.load(
                        self._conversation_session_name
                    )
                    await self._snapshot_manager.take_snapshot(
                        f"{timestamp}: {label}",
                        message_count=len(current_msgs),
                    )
                except Exception as snap_err:
                    logger.warning(f"Snapshot skipped: {snap_err}")
            # Header first
            self.append_to_output(f"\n🤖 {timestamp} >>\n")
            session = self._create_sesion_for_llm_task(user_message, attachments)

            # Run the task with stdout/stderr redirected to UI
            self.append_to_output(stylize_faint("\n  🔢 Streaming response..."))

            # Set UI for tool confirmation
            llm_task.set_ui(self)
            llm_task.tool_confirmation = self._confirm_tool_execution
            result_data = await llm_task.async_run(session)

            # Check for final text output
            if result_data is not None:
                if isinstance(result_data, str):
                    self._last_result_data = result_data
                    width = self._get_output_field_width()
                    self.append_to_output("\n")
                    self.append_to_output(
                        render_markdown(
                            result_data, width=width, theme=self._markdown_theme
                        )
                    )

        except asyncio.CancelledError:
            self.append_to_output("\n[Cancelled]\n")
            raise  # Re-raise to allow proper task cancellation
        except Exception as e:
            self.append_to_output(f"\n[Error: {e}]\n")
        finally:
            self._is_thinking = False
            self._running_llm_task = None
            await self._update_system_info()
            self.invalidate_ui()

    def _create_sesion_for_llm_task(
        self,
        user_message: str,
        attachments: list["UserContent"],
    ) -> AnySession:
        """Create session to run LLMTask"""
        session_input = {
            "message": user_message,
            "session": self._conversation_session_name,
            "yolo": self.yolo,
            "attachments": attachments,
            "model": self._model,
        }
        shared_ctx = SharedContext(
            input=session_input,
            print_fn=self.append_to_output,
            is_web_mode=True,
        )
        return Session(shared_ctx)

    async def _confirm_tool_execution(
        self,
        call: "ToolCallPart",
    ) -> "ToolApproved | ToolDenied | None":
        # Use current_ui context variable to get the correct UI (e.g., BufferedUI for parallel agents)
        # instead of self, which is the captured main UI
        from zrb.llm.agent.runtime_state import get_current_ui
        from zrb.llm.ui.multi_ui import MultiUI

        ui = get_current_ui() or self
        # Handle list of UIs from outer context
        if isinstance(ui, list):
            if len(ui) == 0:
                ui = self
            elif len(ui) == 1:
                ui = ui[0]
            else:
                ui = MultiUI(ui)
        return await self._tool_call_handler.handle(
            ui, call
        )  # --- SYSTEM INFO / TRIGGERS (Moved from UI) ---

    async def _update_system_info(self):
        """Update CWD and Git info."""
        self._cwd = self._get_cwd_display()
        branch, status = await self._get_git_info()
        if branch:
            self._git_info = f"{branch}{status}"
        else:
            self._git_info = "Not a git repo"
        self.invalidate_ui()

    def _get_cwd_display(self) -> str:
        cwd = os.getcwd()
        home = os.path.expanduser("~")
        if cwd.startswith(home):
            return "~" + cwd[len(home) :]
        return cwd

    async def _get_git_info(self) -> tuple[str, str]:
        """Returns (branch_name, status_symbol)"""
        try:
            # Check branch
            proc = await asyncio.create_subprocess_exec(
                "git",
                "rev-parse",
                "--abbrev-ref",
                "HEAD",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode != 0:
                return "", ""
            branch = stdout.decode().strip()

            # Check status (dirty or clean)
            proc = await asyncio.create_subprocess_exec(
                "git",
                "status",
                "--porcelain",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            is_dirty = bool(stdout.strip())

            return branch, "*" if is_dirty else ""
        except Exception:
            return "", ""

    async def _update_system_info_loop(self):
        """Periodically update CWD and Git info."""
        while True:
            try:
                await self._update_system_info()
            except asyncio.CancelledError:
                break
            except Exception:
                pass
            try:
                await asyncio.sleep(CFG.LLM_UI_LONG_STATUS_INTERVAL / 1000)
            except RuntimeError:
                # Event loop closed during shutdown
                break

    async def _trigger_loop(
        self,
        trigger_factory: Callable[[], AsyncIterable[Any]],
    ):
        """Handle external triggers and submit user message when trigger activated"""
        try:
            # 1. Get the iterator
            iterator = trigger_factory()
            if inspect.isawaitable(iterator):
                iterator = await iterator
            # 2. Iterate
            if hasattr(iterator, "__aiter__"):
                # Async Iterator
                async_iter = iterator.__aiter__()
                while True:
                    try:
                        result = await async_iter.__anext__()
                    except StopAsyncIteration:
                        break
                    if result:
                        self._submit_user_message(self._llm_task, str(result))
            else:
                self.append_to_output(
                    stylize_error(
                        f"\n[Trigger Error: Trigger factory returned non-async iterator: {type(iterator)}]\n"
                    )
                )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.append_to_output(stylize_error(f"\n[Trigger Error: {e}]\n"))

    # --- COMMAND HANDLERS live in BaseUICommandsMixin (see _commands_mixin.py) ---
    # The methods _handle_*, _run_shell_command, _stream_btw_response,
    # _submit_attachment, toggle_yolo, and _get_help_text are inherited.
