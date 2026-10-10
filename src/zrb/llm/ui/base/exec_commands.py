"""`/exec`, `/btw` and custom-command handlers for `BaseUI`.

Each `handle_*` returns ``True`` if the input was consumed.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING

from zrb.llm.config.model_resolver import resolve_configured_model
from zrb.llm.custom_command.resolver import get_custom_command_match, run_custom_command
from zrb.llm.prompt.prompt import get_prompt
from zrb.llm.task.shared_getters import apply_model_hooks
from zrb.llm.ui.base.message_queue import QueuedMessage
from zrb.util.cli.style import stylize_error, stylize_muted
from zrb.util.cmd.command import terminate_process, wait_for_exit_and_drain
from zrb.util.exception import exception_summary

if TYPE_CHECKING:
    from zrb.llm.task.llm_task import LLMTask
    from zrb.llm.ui.base.ui import BaseUI


class BaseUIExecCommands:
    """Shell-exec / side-question / custom-command handlers for BaseUI."""

    def __init__(self, base_ui: "BaseUI") -> None:
        self._base_ui = base_ui

    # exec (shell)

    def handle_exec_command(self, text: str) -> bool:
        if self._base_ui.is_thinking:
            return False

        for cmd in self._base_ui.exec_commands:
            prefix = f"{cmd} "
            if text.strip().lower().startswith(prefix):
                shell_cmd = text.strip()[len(prefix) :].strip()
                if not shell_cmd:
                    return True

                entry = QueuedMessage(
                    text=shell_cmd,
                    attachments=[],
                    kind="exec",
                    run=lambda: self.run_shell_command(entry.text),
                )
                self._base_ui.effective_message_queue.put_nowait(entry)
                return True
        return False

    async def run_shell_command(self, cmd: str):
        self._base_ui.is_thinking = True
        self._base_ui.invalidate_ui()
        timestamp = datetime.now().strftime("%H:%M")
        process = None

        try:
            self._base_ui.append_to_output(f"\n💻 {timestamp} >> {cmd}\n")
            self._base_ui.append_to_output(stylize_muted("\n  🔢 Executing...\n"))

            # Shell on purpose: cmd is what the user typed into /exec. Own
            # session so whatever it backgrounds is stopped with it.
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )

            async def read_stream(stream):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    decoded_line = line.decode("utf-8", errors="replace")
                    self._base_ui.append_to_output(decoded_line, end="")

            readers = asyncio.gather(
                read_stream(process.stdout),
                read_stream(process.stderr),
            )
            return_code = await wait_for_exit_and_drain(
                process,
                readers,
                reporter=self._base_ui.append_to_output,
            )
            # `cmd &` is not left running: /exec ends with everything it started.
            await _stop_process(process)

            if return_code == 0:
                self._base_ui.append_to_output(
                    stylize_muted("\n  ✅ Command finished successfully.\n")
                )
            else:
                self._base_ui.append_to_output(
                    stylize_error(
                        f"\n  ❌ Command failed with exit code {return_code}.\n"
                    )
                )

        except asyncio.CancelledError:
            # Reap the child before touching the UI, so an output failure
            # during teardown cannot orphan the process.
            await _stop_process(process)
            self._base_ui.append_to_output("\n[Cancelled]\n")
            raise
        except Exception as e:
            await _stop_process(process)
            self._base_ui.append_to_output(f"\n[Error: {exception_summary(e)}]\n")
        finally:
            self._base_ui.is_thinking = False
            self._base_ui.running_llm_task = None
            await self._base_ui.update_system_info()
            self._base_ui.invalidate_ui()

    # /btw side question

    def handle_btw_command(self, text: str) -> bool:
        """Handle /btw <question>: a side question not saved to history.

        Runs as a background task, bypassing the message queue.
        """
        text = text.strip()
        for cmd in self._base_ui.btw_commands:
            prefix = f"{cmd} "
            if text.lower().startswith(prefix):
                question = text[len(prefix) :].strip()
                if not question:
                    continue

                async def job(q=question):
                    # Via `_base_ui` so a subclass/test override is honored.
                    await self._base_ui.stream_btw_response(self._base_ui.llm_task, q)

                task = asyncio.create_task(job())
                self._base_ui.background_tasks.add(task)
                task.add_done_callback(self._base_ui.background_tasks.discard)
                return True
        return False

    async def stream_btw_response(self, llm_task: "LLMTask", question: str):
        """Answer *question* with a fresh tool-less agent, unsaved to history."""
        try:
            timestamp = datetime.now().strftime("%H:%M")
            self._base_ui.append_to_output(f"\n💭 {timestamp} >> {question.strip()}\n")
            self._base_ui.append_to_output(
                stylize_muted("  (side question — not saved to history)\n")
            )

            # lazy: heavy transitive (pydantic_ai) via zrb.llm.agent
            from zrb.llm.agent import create_agent
            from zrb.llm.agent.types import ModelRequest, SystemPromptPart

            # Strip SystemPromptParts so the main agent's system prompt doesn't
            # conflict with the btw agent's own.
            raw_history = self._base_ui.history_manager.load(
                self._base_ui.conversation_session_name
            )
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

            # The main prompt instructs tool use; this agent has no tools.
            _sys_prompt = get_prompt("side_question")
            # `/model` stores the typed name, so resolve it against the
            # configured credentials (falling back to CFG's model).
            model = resolve_configured_model(self._base_ui.model or None)
            final_model = apply_model_hooks(
                model, llm_task.model_getter, llm_task.model_renderer
            )
            agent = create_agent(
                model=final_model,
                system_prompt=_sys_prompt,
                # No tools on this path; yolo=True keeps the output type
                # plain `str` instead of widening to `str | DeferredToolRequests`.
                yolo=True,
                resolve_model=False,
            )

            self._base_ui.append_to_output(f"\n🤖 {timestamp} >>\n")
            result = await agent.run(question, message_history=btw_history)
            answer = result.output if hasattr(result, "output") else str(result)

            self._base_ui.append_to_output("\n")
            self._base_ui.append_markdown(answer)

        except asyncio.CancelledError:
            self._base_ui.append_to_output("\n[Cancelled]\n")
            raise
        except Exception as e:
            self._base_ui.append_to_output(f"\n[Error: {exception_summary(e)}]\n")
        finally:
            self._base_ui.invalidate_ui()

    # custom commands

    def handle_custom_command(self, text: str) -> bool:
        text = text.strip()
        if not text:
            return False
        if self._base_ui.is_thinking:
            match = get_custom_command_match(text, self._base_ui.custom_commands)
            if match is None or not match[0].can_run_while_thinking:
                return False

        outcome = run_custom_command(text, self._base_ui.custom_commands, self._base_ui)
        if outcome is None:
            return False
        if outcome.prompt is not None:
            self._base_ui.submit_message(outcome.prompt)
        elif outcome.reply:
            self._base_ui.append_to_output(stylize_muted(f"\n  {outcome.reply}\n"))
        return True


async def _stop_process(process: "asyncio.subprocess.Process | None") -> None:
    """Terminate *process* and anything left in its session, then reap it."""
    if process is not None:
        await terminate_process(process, grace_seconds=1.0)
