"""Execution slash-commands for `BaseUI`.

Shell exec (`/exec`), side questions (`/btw`), and user-defined custom
commands. Split out of `commands_mixin.py`; the handlers run on the composed
`BaseUI` instance (see the host-class contract below), mirroring
`CommandsMixin`.

Each `_handle_*` returns ``True`` if the input was consumed, ``False``
otherwise.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING

from zrb.llm.custom_command.resolver import resolve_custom_command
from zrb.util.cli.markdown import render_markdown
from zrb.util.cli.style import stylize_error, stylize_muted

if TYPE_CHECKING:
    from typing import Any

    from rich.theme import Theme

    from zrb.context.any_context import AnyContext
    from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
    from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
    from zrb.llm.task.llm_task import LLMTask
    from zrb.task.any_task import AnyTask


class ExecCommandsMixin:
    """Shell-exec / side-question / custom-command handlers for BaseUI."""

    # Host-class contract: state and methods owned by `BaseUI`. Declared here
    # so type checkers can verify accesses; the block does not run at runtime.
    if TYPE_CHECKING:
        _background_tasks: set[asyncio.Task]
        _btw_commands: list[str]
        _custom_commands: list["AnyCustomCommand"]
        _exec_commands: list[str]
        _conversation_session_name: str
        _history_manager: "AnyHistoryManager"
        _is_thinking: bool
        _llm_task: "LLMTask"
        _markdown_theme: "Theme | None"
        _message_queue: asyncio.Queue
        _model: "Any"
        _running_llm_task: asyncio.Task | None

        @property
        def ctx(self) -> "AnyContext": ...

        def append_to_output(self, *values: Any, **kwargs: Any) -> None: ...

        def invalidate_ui(self) -> None: ...

        async def _update_system_info(self) -> None: ...

        def _get_output_field_width(self) -> int | None: ...

        def _submit_user_message(
            self, llm_task: "AnyTask", user_message: str
        ) -> None: ...

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
        process = None

        try:
            self.append_to_output(f"\n💻 {timestamp} >> {cmd}\n")
            self.append_to_output(stylize_muted("\n  🔢 Executing...\n"))

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
                    stylize_muted("\n  ✅ Command finished successfully.\n")
                )
            else:
                self.append_to_output(
                    stylize_error(
                        f"\n  ❌ Command failed with exit code {return_code}.\n"
                    )
                )

        except asyncio.CancelledError:
            self.append_to_output("\n[Cancelled]\n")
            if process is not None and process.returncode is None:
                try:
                    process.terminate()
                    await asyncio.wait_for(process.wait(), timeout=1.0)
                except Exception:
                    try:
                        process.kill()
                    except Exception:
                        # Best-effort kill during teardown; re-raise below regardless.
                        pass
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
                task = asyncio.create_task(job())
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
                stylize_muted("  (side question — not saved to history)\n")
            )

            # Load current history for context (read-only snapshot).
            # Strip SystemPromptPart entries so the main agent's system prompt
            # doesn't conflict with the btw agent's own system prompt.
            # lazy: heavy third-party
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

            _sys_prompt = (
                llm_task.get_system_prompt(self.ctx)
                + "\n\nAnswer the user's question concisely using this information when relevant."
            )
            # Use the UI's selected model if set (from /model command), otherwise fallback
            model = self._model if self._model else llm_task.llm_config.model
            final_model = llm_task.llm_config.resolve_model(model)
            agent = Agent(
                model=final_model,
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

    # --- custom commands --------------------------------------------------

    def _handle_custom_command(self, text: str) -> bool:
        # Prevent custom commands when LLM is thinking
        if self._is_thinking:
            return False

        text = text.strip()
        if not text:
            return False

        prompt = resolve_custom_command(text, self._custom_commands)
        if prompt is not None:
            self._submit_user_message(self._llm_task, prompt)
            return True
        return False
