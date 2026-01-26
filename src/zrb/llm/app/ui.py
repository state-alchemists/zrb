from __future__ import annotations

import asyncio
import inspect
import os
import re
import shlex
import subprocess
from collections.abc import AsyncIterable, Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any, TextIO

from prompt_toolkit import Application
from prompt_toolkit.application import get_app, run_in_terminal
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import AnyFormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.output import create_output
from prompt_toolkit.styles import Style

from zrb.context.shared_context import SharedContext
from zrb.llm.app.keybinding import create_output_keybindings
from zrb.llm.app.layout import create_input_field, create_layout, create_output_field
from zrb.llm.app.redirection import GlobalStreamCapture
from zrb.llm.app.style import create_style
from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
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
from zrb.util.ascii_art.banner import create_banner
from zrb.util.cli.markdown import render_markdown
from zrb.util.cli.style import stylize_error, stylize_faint
from zrb.util.string.name import get_random_name

if TYPE_CHECKING:
    from pydantic_ai import ToolApproved, ToolCallPart, ToolDenied, UserContent
    from pydantic_ai.models import Model
    from rich.theme import Theme


class UI:
    def __init__(
        self,
        greeting: str,
        assistant_name: str,
        ascii_art: str,
        jargon: str,
        output_lexer: Lexer,
        llm_task: LLMTask,
        history_manager: AnyHistoryManager,
        initial_message: Any = "",
        initial_attachments: list[UserContent] = [],
        conversation_session_name: str = "",
        yolo: bool = False,
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
        exec_commands: list[str] = [],
        custom_commands: list[AnyCustomCommand] = [],
        model: "Model | str | None" = None,
    ):
        self._is_thinking = False
        self._running_llm_task: asyncio.Task | None = None
        self._llm_task = llm_task
        self._history_manager = history_manager
        self._assistant_name = assistant_name
        self._ascii_art = ascii_art
        self._jargon = jargon
        self._initial_message = initial_message
        self._conversation_session_name = conversation_session_name
        if not self._conversation_session_name:
            self._conversation_session_name = get_random_name()
        self._yolo = yolo
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
        self._exec_commands = exec_commands
        self._custom_commands = custom_commands
        self._trigger_tasks: list[asyncio.Task] = []
        self._last_result_data: str | None = None
        # System Info
        self._cwd = os.getcwd()
        self._git_info = "Checking..."
        self._system_info_task: asyncio.Task | None = None
        # Attachments
        self._pending_attachments: list[UserContent] = list(initial_attachments)
        # Confirmation Handler
        self._tool_call_handler = ToolCallHandler(
            tool_policies=tool_policies,
            argument_formatters=argument_formatters,
            response_handlers=response_handlers + [default_response_handler],
        )
        # Confirmation state (Used by ask_user and keybindings)
        self._waiting_for_confirmation = False
        self._confirmation_future: asyncio.Future[str] | None = None
        # Output Capture
        self._capture = GlobalStreamCapture(self.append_to_output)
        # UI Styles
        self._style = create_style()
        # Input Area
        self._input_field = create_input_field(
            history_manager=self._history_manager,
            attach_commands=self._attach_commands,
            exit_commands=self._exit_commands,
            info_commands=self._info_commands,
            save_commands=self._save_commands,
            load_commands=self._load_commands,
            redirect_output_commands=self._redirect_output_commands,
            summarize_commands=self._summarize_commands,
            exec_commands=self._exec_commands,
            custom_commands=self._custom_commands,
        )
        # Output Area (Read-only chat history)
        help_text = self._get_help_text()
        full_greeting = create_banner(self._ascii_art, f"{greeting}\n{help_text}")
        self._output_field = create_output_field(full_greeting, output_lexer)
        self._output_field.control.key_bindings = create_output_keybindings(
            self._input_field
        )
        self._layout = create_layout(
            title=self._assistant_name,
            jargon=self._jargon,
            input_field=self._input_field,
            output_field=self._output_field,
            info_bar_text=self._get_info_bar_text,
            status_bar_text=self._get_status_bar_text,
        )
        # Key Bindings
        self._app_kb = KeyBindings()
        self._setup_app_keybindings(
            app_keybindings=self._app_kb, llm_task=self._llm_task
        )
        # Application
        self._application = self._create_application(
            layout=self._layout, keybindings=self._app_kb, style=self._style
        )
        # Send message if first_message is provided. Make sure only run at most once
        if self._initial_message:
            self._application.after_render.add_handler(self._on_first_render)

    async def run_async(self):
        """Run the application and manage triggers."""
        # Start triggers
        for trigger_fn in self._triggers:
            trigger_task = self._application.create_background_task(
                self._trigger_loop(trigger_fn)
            )
            self._trigger_tasks.append(trigger_task)

        # Start system info update loop
        self._system_info_task = self._application.create_background_task(
            self._update_system_info_loop()
        )

        try:
            self._capture.start()
            return await self._application.run_async()
        finally:
            self._capture.stop()

            # Stop triggers
            for trigger_task in self._trigger_tasks:
                trigger_task.cancel()
            self._trigger_tasks.clear()

            if self._system_info_task:
                self._system_info_task.cancel()

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

        except asyncio.CancelledError:
            pass
        except Exception:
            # Keep running on error, maybe log it
            pass

    async def _update_system_info_loop(self):
        """Periodically update CWD and Git info."""
        while True:
            try:
                self._cwd = self._get_cwd_display()
                branch, status = await self._get_git_info()
                if branch:
                    self._git_info = f"{branch}{status}"
                else:
                    self._git_info = "Not a git repo"
                get_app().invalidate()
            except asyncio.CancelledError:
                break
            except Exception:
                pass
            await asyncio.sleep(2)

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

    def _on_first_render(self, app: Application):
        """Handle initial message (the message sent when creating the UI)"""
        self._application.after_render.remove_handler(self._on_first_render)
        self._submit_user_message(self._llm_task, self._initial_message)

    async def ask_user(self, prompt: str) -> str:
        """Prompts the user for input via the main input field, blocking until provided."""
        self._waiting_for_confirmation = True
        self._confirmation_future = asyncio.Future()

        if prompt:
            self.append_to_output(prompt, end="")

        get_app().invalidate()

        try:
            return await self._confirmation_future
        finally:
            self._waiting_for_confirmation = False
            self._confirmation_future = None

    async def _confirm_tool_execution(
        self,
        call: ToolCallPart,
    ) -> ToolApproved | ToolDenied | None:
        return await self._tool_call_handler.handle(self, call)

    async def run_interactive_command(
        self, cmd: str | list[str], shell: bool = False
    ) -> Any:
        def run_subprocess():
            # Run the command. Standard streams will inherit from the parent,
            # which have been restored to the TTY by self._capture.pause()
            subprocess.call(cmd, shell=shell)

        # Pause capture and await run_in_terminal.
        # It's crucial to await so the pause() context manager stays active
        # until the subprocess (e.g. vim) finishes.
        with self._capture.pause():
            await run_in_terminal(run_subprocess)

    @property
    def triggers(
        self,
    ) -> list[Callable[[], AsyncIterable[Any]]]:
        return self._triggers

    @triggers.setter
    def triggers(
        self,
        value: list[Callable[[], AsyncIterable[Any]]],
    ):
        self._triggers = value

    @property
    def application(self) -> Application:
        return self._application

    @property
    def last_output(self) -> str:
        if self._last_result_data is None:
            return ""
        return self._last_result_data

    def _create_application(
        self,
        layout: Layout,
        keybindings: KeyBindings,
        style: Style,
    ) -> Application:
        try:
            from prompt_toolkit.clipboard.pyperclip import PyperclipClipboard

            clipboard = PyperclipClipboard()
        except ImportError:
            clipboard = None

        return Application(
            layout=layout,
            key_bindings=keybindings,
            style=style,
            full_screen=True,
            mouse_support=True,
            refresh_interval=0.1,
            output=create_output(stdout=self._capture.get_original_stdout()),
            clipboard=clipboard,
        )

    def _get_help_text(self) -> str:
        help_lines = ["\nAvailable Commands:"]

        def add_cmd_help(commands: list[str], description: str):
            if commands and len(commands) > 0:
                cmd = commands[0]
                description = description.replace("{cmd}", cmd)
                help_lines.append(f"  {cmd:<10} : {description}")

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
        add_cmd_help(
            self._exec_commands, "Execute shell command (usage: {cmd} <command>)"
        )
        for custom_cmd in self._custom_commands:
            usage = f"{custom_cmd.command} " + " ".join(
                [f"<{a}>" for a in custom_cmd.args]
            )
            help_lines.append(f"  {custom_cmd.command:<10} : {usage}")

        return "\n".join(help_lines) + "\n"

    def _get_info_bar_text(self) -> AnyFormattedText:
        from prompt_toolkit.formatted_text import HTML

        model_name = "Unknown"
        if self._model:
            if isinstance(self._model, str):
                model_name = self._model
            elif hasattr(self._model, "model_name"):
                model_name = getattr(self._model, "model_name")
            else:
                model_name = str(self._model)
        yolo_text = (
            "<style color='ansired'><b>ON</b></style>"
            if self._yolo
            else "<style color='ansigreen'>OFF</style>"
        )
        return HTML(
            f" 🤖 <b>Model:</b> {model_name} "
            f"| 🗣️ <b>Session:</b> {self._conversation_session_name} "
            f"| 🤠 <b>YOLO:</b> {yolo_text} \n"
            f" 📂 <b>Dir:</b> {self._cwd} "
            f"| 🌿 <b>Git:</b> {self._git_info} "
        )

    def _get_status_bar_text(self) -> AnyFormattedText:
        if self._is_thinking:
            return [("class:thinking", f" {self._assistant_name} is thinking... ")]
        return [("class:status", " Ready ")]

    def _setup_app_keybindings(self, app_keybindings: KeyBindings, llm_task: AnyTask):
        @app_keybindings.add("c-c")
        def _(event):
            # If text is selected, copy it instead of exiting
            buffer = event.app.current_buffer
            if buffer.selection_state:
                data = buffer.copy_selection()
                event.app.clipboard.set_data(data)
                buffer.exit_selection()
                return
            # If buffer is not empty, clear it
            if buffer.text != "":
                buffer.reset()
                return
            event.app.exit()

        @app_keybindings.add("escape")
        def _(event):
            if self._running_llm_task and not self._running_llm_task.done():
                self._running_llm_task.cancel()
                self.append_to_output("\n<Esc> Canceled")

        @app_keybindings.add("enter")
        def _(event):
            # Handle confirmation and multiline
            if self._handle_confirmation(event):
                return
            if self._handle_multiline(event):
                return

            # Handle empty inputs
            buff = event.current_buffer
            text = buff.text
            if not text.strip():
                return

            # Handle other commands
            if self._handle_exit_command(event):
                return
            if self._handle_info_command(event):
                return
            if self._handle_save_command(event):
                return
            if self._handle_load_command(event):
                return
            if self._handle_redirect_command(event):
                return
            if self._handle_attach_command(event):
                return
            if self._handle_toggle_yolo(event):
                return
            if self._handle_exec_command(event):
                return
            if self._handle_custom_command(event):
                return

            # If we are thinking, ignore input
            if self._is_thinking:
                return
            self._submit_user_message(llm_task, text)
            buff.reset()

        @app_keybindings.add("c-j")  # Ctrl+J
        @app_keybindings.add("c-space")  # Ctrl+Space (Fallback)
        def _(event):
            event.current_buffer.insert_text("\n")

    def _handle_exec_command(self, event) -> bool:
        buff = event.current_buffer
        text = buff.text
        for cmd in self._exec_commands:
            prefix = f"{cmd} "
            if text.strip().lower().startswith(prefix):
                if self._is_thinking:
                    return False

                shell_cmd = text.strip()[len(prefix) :].strip()
                if not shell_cmd:
                    return True

                buff.reset()
                # Run in background
                self._running_llm_task = asyncio.create_task(
                    self._run_shell_command(shell_cmd)
                )
                return True
        return False

    def _handle_custom_command(self, event) -> bool:
        buff = event.current_buffer
        text = buff.text.strip()
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
                buff.reset()
                self._submit_user_message(self._llm_task, prompt)
                return True
        return False

    async def _run_shell_command(self, cmd: str):
        self._is_thinking = True
        get_app().invalidate()
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
            is_first_output = True

            # Read output streams
            async def read_stream(stream, is_stderr=False):
                while True:
                    nonlocal is_first_output
                    line = await stream.readline()
                    if not line:
                        break
                    decoded_line = line.decode("utf-8", errors="replace")
                    decoded_line = decoded_line.replace("\n", "\n  ").replace(
                        "\r", "\r  "
                    )
                    if is_first_output:
                        decoded_line = f"  {decoded_line}"
                        is_first_output = False
                    # Could use a different color for stderr if desired
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
        except Exception as e:
            self.append_to_output(f"\n[Error: {e}]\n")
        finally:
            self._is_thinking = False
            self._running_llm_task = None
            get_app().invalidate()

    def _handle_toggle_yolo(self, event) -> bool:
        buff = event.current_buffer
        text = buff.text
        if text.strip().lower() in self._yolo_toggle_commands:
            if self._is_thinking:
                return False
            self._yolo = not self._yolo
            buff.reset()
            return True
        return False

    def _handle_multiline(self, event) -> bool:
        buff = event.current_buffer
        text = buff.text
        # Check for multiline indicator (trailing backslash)
        if text.strip().endswith("\\"):
            # If cursor is at the end, remove backslash and insert newline
            if buff.cursor_position == len(text):
                # Remove the backslash (assuming it's the last char)
                # We need to be careful with whitespace after backslash if we used strip()
                # Let's just check the character before cursor
                if text.endswith("\\"):
                    buff.delete_before_cursor(count=1)
                    buff.insert_text("\n")
                    return True
        return False

    def _handle_confirmation(self, event) -> bool:
        buff = event.current_buffer
        text = buff.text
        if self._waiting_for_confirmation and self._confirmation_future:
            # Echo the user input
            self.append_to_output(text + "\n")
            if not self._confirmation_future.done():
                self._confirmation_future.set_result(text)
            buff.reset()
            return True
        return False

    def _handle_exit_command(self, event) -> bool:
        buff = event.current_buffer
        text = buff.text
        if text.strip().lower() in self._exit_commands:
            event.app.exit()
            return True
        return False

    def _handle_info_command(self, event) -> bool:
        buff = event.current_buffer
        text = buff.text
        if text.strip().lower() in self._info_commands:
            self.append_to_output(stylize_faint(self._get_help_text()))
            buff.reset()
            return True
        return False

    def _handle_save_command(self, event) -> bool:
        buff = event.current_buffer
        text = buff.text.strip()
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
                buff.reset()
                return True
        return False

    def _handle_load_command(self, event) -> bool:
        buff = event.current_buffer
        text = buff.text.strip()
        for cmd in self._load_commands:
            prefix = f"{cmd} "
            if text.lower().startswith(prefix):
                name = text[len(prefix) :].strip()
                if not name:
                    continue
                self._conversation_session_name = name
                self.append_to_output(
                    stylize_faint(f"\n  📂 Conversation session switched to: {name}\n")
                )
                buff.reset()
                return True
        return False

    def _handle_redirect_command(self, event) -> bool:
        buff = event.current_buffer
        text = buff.text.strip()
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
                    buff.reset()
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

                buff.reset()
                return True
        return False

    def _handle_attach_command(self, event) -> bool:
        buff = event.current_buffer
        text = buff.text
        for attach_command in self._attach_commands:
            if text.strip().lower().startswith(f"{attach_command} "):
                path = text.strip()[8:].strip()
                self._submit_attachment(path)
                buff.reset()
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

    def append_to_output(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
    ):
        # Helper to safely append to read-only buffer
        current_text = self._output_field.text

        # Construct the new content
        content = sep.join([str(value) for value in values]) + end

        # Handle carriage returns (\r) for status updates
        if "\r" in content:
            # Find the start of the last line in the current text
            last_newline = current_text.rfind("\n")
            if last_newline == -1:
                previous = ""
                last = current_text
            else:
                previous = current_text[: last_newline + 1]
                last = current_text[last_newline + 1 :]

            combined = last + content
            # Remove content before \r on the same line
            # [^\n]* matches any character except newline
            resolved = re.sub(r"[^\n]*\r", "", combined)

            new_text = previous + resolved
        else:
            new_text = current_text + content

        # Update content directly
        # We use bypass_readonly=True by constructing a Document
        self._output_field.buffer.set_document(
            Document(new_text, cursor_position=len(new_text)), bypass_readonly=True
        )
        get_app().invalidate()

    def _submit_user_message(self, llm_task: AnyTask, user_message: str):
        timestamp = datetime.now().strftime("%H:%M")
        # 1. Render User Message
        self.append_to_output(f"\n💬 {timestamp} >> {user_message.strip()}\n")
        # 2. Trigger AI Response
        attachments = list(self._pending_attachments)
        self._pending_attachments.clear()
        self._running_llm_task = asyncio.create_task(
            self._stream_ai_response(llm_task, user_message, attachments)
        )

    async def _stream_ai_response(
        self,
        llm_task: LLMTask,
        user_message: str,
        attachments: list[UserContent] = [],
    ):
        self._is_thinking = True
        get_app().invalidate()  # Update status bar
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
        except Exception as e:
            self.append_to_output(f"\n[Error: {e}]\n")
        finally:
            self._is_thinking = False
            self._running_llm_task = None
            get_app().invalidate()

    def _create_sesion_for_llm_task(
        self,
        user_message: str,
        attachments: list[UserContent],
    ) -> AnySession:
        """Create session to run LLMTask"""
        session_input = {
            "message": user_message,
            "session": self._conversation_session_name,
            "yolo": self._yolo,
            "attachments": attachments,
        }
        shared_ctx = SharedContext(
            input=session_input,
            print_fn=self.append_to_output,
            is_web_mode=True,
        )
        return Session(shared_ctx)

    def _get_output_field_width(self) -> int | None:
        try:
            width = get_app().output.get_size().columns - 4
            if width < 10:
                width = None
        except Exception:
            width = None
        return width
