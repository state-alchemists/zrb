import asyncio
import inspect
import logging
import os
import shlex
from collections.abc import AsyncIterable, Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any, TextIO

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


class BaseUI:
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
                            await asyncio.sleep(1)
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
        is_yolo: bool = False,
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
        redirect_output_commands: list[str] = [],
        yolo_toggle_commands: list[str] = [],
        set_model_commands: list[str] = [],
        exec_commands: list[str] = [],
        btw_commands: list[str] = [],
        custom_commands: list[AnyCustomCommand] = [],
        model: "Model | str | None" = None,
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
    def yolo(self) -> bool:
        if self._yolo_xcom_key not in self._ctx.xcom:
            return False
        return self._ctx.xcom[self._yolo_xcom_key].get(False)

    @yolo.setter
    def yolo(self, value: bool):
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
                    await asyncio.sleep(1)
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
        from zrb.llm.agent.run_agent import current_ui
        from zrb.llm.ui.multi_ui import MultiUI

        ui = current_ui.get() or self
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
                await asyncio.sleep(60)
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
            self.append_to_output(
                stylize_error(f"\n[Trigger Error: {e}]\n")
            )  # --- COMMAND HANDLERS (Moved from UI) ---

    def _handle_exit_command(self, text: str) -> bool:
        if text.strip().lower() in self._exit_commands:
            self.on_exit()
            return True
        return False

    def _handle_info_command(self, text: str) -> bool:
        if text.strip().lower() in self._info_commands:
            self.append_to_output(stylize_faint(self._get_help_text()))
            return True
        return False

    def _handle_save_command(self, text: str) -> bool:
        text = text.strip()
        for cmd in self._save_commands:
            prefix = f"{cmd} "
            if text.lower().startswith(prefix):
                name = text[len(prefix) :].strip()
                if not name:
                    continue
                try:
                    history = self._history_manager.load(
                        self._conversation_session_name
                    )
                    self._history_manager.update(name, history)
                    self._history_manager.save(name)
                    self.append_to_output(
                        stylize_faint(f"\n  💾 Conversation saved as: {name}\n")
                    )
                except Exception as e:
                    self.append_to_output(
                        stylize_error(f"\n  ❌ Failed to save conversation: {e}\n")
                    )
                return True
        return False

    def _handle_load_command(self, text: str) -> bool:
        text = text.strip()
        for cmd in self._load_commands:
            prefix = f"{cmd} "
            if text.lower().startswith(prefix):
                name = text[len(prefix) :].strip()
                if not name:
                    continue
                self._conversation_session_name = name
                # Load and display the conversation history
                try:
                    history = self._history_manager.load(name)
                    from zrb.llm.util.history_formatter import format_history_as_text

                    history_text = format_history_as_text(history)
                    self.append_to_output(stylize_faint(f"\n{history_text}\n"))
                except Exception as e:
                    self.append_to_output(
                        stylize_error(f"\n  ❌ Failed to load history: {e}\n")
                    )
                self.append_to_output(
                    stylize_faint(f"\n  📂 Conversation session switched to: {name}\n")
                )
                return True
        return False

    def _handle_redirect_command(self, text: str) -> bool:
        text = text.strip()
        for cmd in self._redirect_output_commands:
            prefix = f"{cmd} "
            if text.lower().startswith(prefix):
                path = text[len(prefix) :].strip()
                if not path:
                    continue

                content = self.last_output
                if not content:
                    self.append_to_output(
                        stylize_error("\n  ❌ No AI response available to redirect.\n")
                    )
                    return True

                try:
                    # Write to file
                    expanded_path = os.path.abspath(os.path.expanduser(path))
                    os.makedirs(os.path.dirname(expanded_path), exist_ok=True)
                    with open(expanded_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    self.append_to_output(
                        stylize_faint(f"\n  📝 Last output redirected to: {path}\n")
                    )
                except Exception as e:
                    self.append_to_output(
                        stylize_error(f"\n  ❌ Failed to redirect output: {e}\n")
                    )

                return True
        return False

    def _handle_attach_command(self, text: str) -> bool:
        for attach_command in self._attach_commands:
            if text.strip().lower().startswith(f"{attach_command} "):
                path = text.strip()[8:].strip()
                self._submit_attachment(path)
                return True
        return False

    def _submit_attachment(self, path: str):
        # Validate path
        self.append_to_output(stylize_faint(f"\n  🔢 Attach {path}...\n"))
        expanded_path = os.path.abspath(os.path.expanduser(path))
        if not os.path.exists(expanded_path):
            self.append_to_output(stylize_error(f"\n  ❌ File not found: {path}\n"))
            return
        if expanded_path not in self._pending_attachments:
            self._pending_attachments.append(expanded_path)
            self.append_to_output(stylize_faint(f"\n  📎 Attached: {path}\n"))
        else:
            self.append_to_output(stylize_error(f"\n  📎 Already attached: {path}\n"))

    def toggle_yolo(self):
        """Toggle YOLO mode and force refresh."""
        self.yolo = not self.yolo
        self.invalidate_ui()

    def _handle_toggle_yolo(self, text: str) -> bool:
        if text.strip().lower() in self._yolo_toggle_commands:
            self.toggle_yolo()
            return True
        return False

    def _handle_set_model_command(self, text: str) -> bool:
        text = text.strip()
        for cmd in self._set_model_commands:
            prefix = f"{cmd} "
            if text.lower().startswith(prefix):
                if self._is_thinking:
                    return False
                model_name = text[len(prefix) :].strip()
                if not model_name:
                    continue
                self._model = model_name
                self.append_to_output(
                    stylize_faint(f"\n  🤖 Model switched to: {model_name}\n")
                )
                return True
        return False

    def _handle_exec_command(self, text: str) -> bool:
        # Prevent execution when LLM is thinking
        if self._is_thinking:
            return False

        for cmd in self._exec_commands:
            prefix = f"{cmd} "
            if text.strip().lower().startswith(prefix):
                shell_cmd = text.strip()[len(prefix) :].strip()
                if not shell_cmd:
                    return True

                async def job():
                    await self._run_shell_command(shell_cmd)

                self._message_queue.put_nowait(job)
                return True
        return False

    async def _run_shell_command(self, cmd: str):
        self._is_thinking = True
        self.invalidate_ui()
        timestamp = datetime.now().strftime("%H:%M")

        try:
            self.append_to_output(f"\n💻 {timestamp} >> {cmd}\n")
            self.append_to_output(stylize_faint("\n  🔢 Executing...\n"))

            # Create subprocess
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Read output streams
            async def read_stream(stream, is_stderr=False):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    decoded_line = line.decode("utf-8", errors="replace")
                    # Indentation is now handled globally by get_line_prefix
                    self.append_to_output(decoded_line, end="")

            await asyncio.gather(
                read_stream(process.stdout), read_stream(process.stderr, is_stderr=True)
            )

            return_code = await process.wait()

            if return_code == 0:
                self.append_to_output(
                    stylize_faint("\n  ✅ Command finished successfully.\n")
                )
            else:
                self.append_to_output(
                    stylize_error(
                        f"\n  ❌ Command failed with exit code {return_code}.\n"
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

    def _handle_btw_command(self, text: str) -> bool:
        """Handle /btw <question> — ask a side question without saving to history.

        Intentionally works while the LLM is thinking (no _is_thinking guard).
        Runs as an independent background task to avoid interfering with the
        main conversation.
        """
        text = text.strip()
        for cmd in self._btw_commands:
            prefix = f"{cmd} "
            if text.lower().startswith(prefix):
                question = text[len(prefix) :].strip()
                if not question:
                    continue

                async def job(q=question):
                    await self._stream_btw_response(self._llm_task, q)

                # Bypass the serializing message queue — run as an independent
                # background task so it executes in parallel with the main LLM.
                task = asyncio.get_event_loop().create_task(job())
                self._background_tasks.add(task)
                task.add_done_callback(self._background_tasks.discard)
                return True
        return False

    async def _stream_btw_response(self, llm_task: LLMTask, question: str):
        """Run an ephemeral LLM query that runs alongside the current conversation.

        Uses a fresh, independent pydantic-ai Agent so there are no race conditions
        with the possibly-running main LLM task (no shared state is mutated).
        The response is never saved to conversation history.
        """
        try:
            timestamp = datetime.now().strftime("%H:%M")
            self.append_to_output(f"\n💭 {timestamp} >> {question.strip()}\n")
            self.append_to_output(
                stylize_faint("  (side question — not saved to history)\n")
            )

            # Load current history for context (read-only snapshot).
            # Strip SystemPromptPart entries so the main agent's system prompt
            # doesn't conflict with the btw agent's own system prompt.
            import platform

            from pydantic_ai import Agent
            from pydantic_ai.messages import ModelRequest, SystemPromptPart

            raw_history = self._history_manager.load(self._conversation_session_name)
            btw_history = []
            for msg in raw_history:
                if isinstance(msg, ModelRequest):
                    clean_parts = [
                        p for p in msg.parts if not isinstance(p, SystemPromptPart)
                    ]
                    if clean_parts:
                        btw_history.append(ModelRequest(parts=clean_parts))
                else:
                    btw_history.append(msg)

            # Create a fresh, independent agent — no shared state with llm_task.
            # Use an explicit instruction so the model uses the provided time
            # rather than falling back to "I have no real-time access".
            _now = datetime.now().strftime("%A, %B %d, %Y %H:%M:%S")
            _sys_prompt = (
                f"The current time is {_now}. "
                f"The OS is {platform.platform()}. "
                f"The current directory is {os.getcwd()}. "
                "Answer the user's question concisely using this information when relevant."
            )
            # Use the UI's selected model if set (from /model command), otherwise fallback
            model = self._model if self._model else llm_task._llm_config.model
            agent = Agent(
                model=model,
                system_prompt=_sys_prompt,
            )

            self.append_to_output(f"\n🤖 {timestamp} >>\n")
            result = await agent.run(question, message_history=btw_history)
            answer = result.output if hasattr(result, "output") else str(result)

            width = self._get_output_field_width()
            self.append_to_output("\n")
            self.append_to_output(
                render_markdown(answer, width=width, theme=self._markdown_theme)
            )

        except asyncio.CancelledError:
            self.append_to_output("\n[Cancelled]\n")
            raise
        except Exception as e:
            self.append_to_output(f"\n[Error: {e}]\n")
        finally:
            self.invalidate_ui()

    def _handle_custom_command(self, text: str) -> bool:
        # Prevent custom commands when LLM is thinking
        if self._is_thinking:
            return False

        text = text.strip()
        if not text:
            return False

        try:
            parts = shlex.split(text)
        except Exception:
            return False

        if not parts:
            return False

        cmd_name = parts[0]
        for custom_cmd in self._custom_commands:
            if cmd_name == custom_cmd.command:
                provided_args = parts[1:]
                # Join residue arguments
                if len(provided_args) > len(custom_cmd.args):
                    num_args = len(custom_cmd.args)
                    if num_args > 0:
                        args_to_keep = provided_args[: num_args - 1]
                        residue = provided_args[num_args - 1 :]
                        joined_residue = " ".join(residue)
                        provided_args = args_to_keep + [joined_residue]

                # Extract arguments
                args_dict = {
                    custom_cmd.args[i]: (
                        provided_args[i] if i < len(provided_args) else ""
                    )
                    for i in range(len(custom_cmd.args))
                }
                prompt = custom_cmd.get_prompt(args_dict)
                self._submit_user_message(self._llm_task, prompt)
                return True
        return False

    def _get_help_text(self, limit: int | None = None) -> str:
        raw_lines: list[tuple[str, str]] = []

        def add_cmd_help(commands: list[str], description: str):
            if commands and len(commands) > 0:
                cmd = commands[0]
                raw_lines.append((cmd, description.replace("{cmd}", cmd)))

        add_cmd_help(self._exit_commands, "Exit the application")
        add_cmd_help(self._info_commands, "Show this help message")
        add_cmd_help(self._attach_commands, "Attach file (usage: {cmd} <path>)")
        add_cmd_help(self._save_commands, "Save conversation (usage: {cmd} <name>)")
        add_cmd_help(self._load_commands, "Load conversation (usage: {cmd} <name>)")
        add_cmd_help(
            self._redirect_output_commands,
            "Save last output to file (usage: {cmd} <file>)",
        )
        add_cmd_help(self._summarize_commands, "Summarize conversation history")
        add_cmd_help(self._yolo_toggle_commands, "Toggle YOLO mode")
        add_cmd_help(self._set_model_commands, "Set model (usage: {cmd} <model-name>)")
        add_cmd_help(
            self._exec_commands, "Execute shell command (usage: {cmd} <command>)"
        )
        add_cmd_help(
            self._btw_commands,
            "Ask a side question without saving to history (usage: {cmd} <question>)",
        )
        for custom_cmd in self._custom_commands:
            usage = f"{custom_cmd.command} " + " ".join(
                [f"<{a}>" for a in custom_cmd.args]
            )
            raw_lines.append((custom_cmd.command, usage))

        if not raw_lines:
            return ""

        max_cmd_len = max(len(cmd) for cmd, _ in raw_lines)
        help_lines = ["\nAvailable Commands:"]
        for i, (cmd, desc) in enumerate(raw_lines):
            if limit is not None and i >= limit:
                help_lines.append("  ... and more")
                break
            help_lines.append(f"  {cmd:<{max_cmd_len}} : {desc}")

        return "\n".join(help_lines) + "\n"
