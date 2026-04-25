"""Slash-command handlers for `BaseUI`.

Each `_handle_*` returns `True` if the input was consumed (a command matched),
`False` otherwise. The mixin assumes the host class provides:
- the standard set of `_*_commands` lists and `_custom_commands` (set in BaseUI.__init__)
- `_history_manager`, `_snapshot_manager`, `_message_queue`, `_pending_attachments`
- `_is_thinking`, `_running_llm_task`, `_background_tasks`, `_llm_task`, `_model`
- `_conversation_session_name`, `_markdown_theme`
- `append_to_output(...)`, `invalidate_ui()`, `last_output`, `_submit_user_message(...)`
- `_update_system_info()`, `_get_output_field_width()`, `yolo` (property), `on_exit()`
"""

from __future__ import annotations

import asyncio
import logging
import os
import shlex
from datetime import datetime
from typing import TYPE_CHECKING

from zrb.util.cli.markdown import render_markdown
from zrb.util.cli.style import stylize_error, stylize_faint

if TYPE_CHECKING:
    from zrb.llm.task.llm_task import LLMTask

logger = logging.getLogger(__name__)


class CommandsMixin:
    """Slash-command dispatch for BaseUI."""

    # --- exit / info ------------------------------------------------------

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

    # --- save / load ------------------------------------------------------

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

    # --- rewind -----------------------------------------------------------

    def _handle_rewind_command(self, text: str) -> bool:
        if not self._snapshot_manager:
            return False
        text = text.strip()
        for cmd in self._rewind_commands:
            if not (
                text.lower() == cmd.lower()
                or text.lower().startswith(cmd.lower() + " ")
            ):
                continue
            arg = text[len(cmd) :].strip()
            if arg:
                snapshots = self._snapshot_manager.list_snapshots()
                sha: str | None = None
                message_count: int | None = None
                try:
                    idx = int(arg) - 1
                    if 0 <= idx < len(snapshots):
                        sha = snapshots[idx].sha
                        message_count = snapshots[idx].message_count
                    else:
                        self.append_to_output(
                            stylize_error(f"\n  ❌ No snapshot at index {arg}\n")
                        )
                        return True
                except ValueError:
                    sha = arg  # treat as SHA prefix/full
                    for snap in snapshots:
                        if snap.sha.startswith(sha):
                            message_count = snap.message_count
                            break

                async def do_restore(s=sha, mc=message_count):
                    self._is_thinking = True
                    self.invalidate_ui()
                    try:
                        self.append_to_output(
                            stylize_faint(f"\n  ⏪ Restoring snapshot {s[:8]}...\n")
                        )
                        ok = await self._snapshot_manager.restore_snapshot(s)
                        if ok:
                            if mc is not None:
                                try:
                                    msgs = self._history_manager.load(
                                        self._conversation_session_name
                                    )
                                    if len(msgs) > mc:
                                        self._history_manager.update(
                                            self._conversation_session_name,
                                            msgs[:mc],
                                        )
                                        self._history_manager.save(
                                            self._conversation_session_name
                                        )
                                except Exception as e:
                                    logger.warning(
                                        f"Failed to rewind conversation history: {e}"
                                    )
                            self.append_to_output(
                                stylize_faint(f"\n  ✅ Snapshot {s[:8]} restored.\n")
                            )
                        else:
                            self.append_to_output(
                                stylize_error("\n  ❌ Failed to restore snapshot.\n")
                            )
                    finally:
                        self._is_thinking = False
                        self.invalidate_ui()

                task = asyncio.get_event_loop().create_task(do_restore())
                self._background_tasks.add(task)
                task.add_done_callback(self._background_tasks.discard)
            else:
                snapshots = self._snapshot_manager.list_snapshots()
                if not snapshots:
                    self.append_to_output(
                        stylize_faint(
                            f"\n  No snapshots yet. Snapshots are taken before each AI turn.\n"
                        )
                    )
                else:
                    lines = ["\n  Snapshots (newest first):"]
                    for i, snap in enumerate(snapshots, 1):
                        lines.append(
                            f"  {i:>3}. [{snap.sha[:8]}] {snap.timestamp}  {snap.label}"
                        )
                    lines.append(
                        f"\n  Use `{cmd} <number>` or `{cmd} <sha>` to restore.\n"
                    )
                    self.append_to_output(stylize_faint("\n".join(lines)))
            return True
        return False

    # --- redirect / attach ------------------------------------------------

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
        text = text.strip()
        for cmd in self._attach_commands:
            prefix = f"{cmd} "
            if text.lower().startswith(prefix):
                path = text[len(prefix) :].strip()
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

    # --- yolo / model -----------------------------------------------------

    def toggle_yolo(self):
        """Toggle YOLO mode (full on/off) and force refresh."""
        self.yolo = not bool(self.yolo)
        self.invalidate_ui()

    def _handle_toggle_yolo(self, text: str) -> bool:
        stripped = text.strip()
        for cmd in self._yolo_toggle_commands:
            if stripped.lower() == cmd.lower():
                # Plain /yolo — toggle full yolo on/off
                self.toggle_yolo()
                return True
            if stripped.lower().startswith(cmd.lower() + " "):
                # /yolo Write,Edit — activate selective yolo for those tools
                tools_str = stripped[len(cmd) :].strip()
                tools = frozenset(t.strip() for t in tools_str.split(",") if t.strip())
                if tools:
                    self.yolo = tools
                    self.invalidate_ui()
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

    # --- exec (shell) -----------------------------------------------------

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

            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            async def read_stream(stream, is_stderr=False):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    decoded_line = line.decode("utf-8", errors="replace")
                    self.append_to_output(decoded_line, end="")

            await asyncio.gather(
                read_stream(process.stdout),
                read_stream(process.stderr, is_stderr=True),
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

    # --- /btw side question -----------------------------------------------

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

    async def _stream_btw_response(self, llm_task: "LLMTask", question: str):
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

    # --- custom commands + help text -------------------------------------

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
        if self._snapshot_manager is not None:
            add_cmd_help(
                self._rewind_commands,
                "List snapshots or restore one (usage: {cmd} [<n>|<sha>])",
            )
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
