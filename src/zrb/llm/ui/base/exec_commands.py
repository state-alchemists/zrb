"""Execution slash-commands for `BaseUI`.

Shell exec (`/exec`), side questions (`/btw`), and user-defined custom
commands. Split out of `commands.py`. Composed into `BaseUICommands` as
`self._exec`, keeping `BaseUI` in `self._base_ui` for state and method
calls.

Each `_handle_*` returns ``True`` if the input was consumed, ``False``
otherwise.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING

from zrb.llm.config.model_resolver import resolve_configured_model
from zrb.llm.custom_command.resolver import resolve_custom_command
from zrb.llm.task.shared_getters import apply_model_hooks
from zrb.llm.ui.base.message_queue import QueuedMessage
from zrb.util.cli.style import stylize_error, stylize_muted

if TYPE_CHECKING:
    from zrb.llm.task.llm_task import LLMTask
    from zrb.llm.ui.base.ui import BaseUI


class BaseUIExecCommands:
    """Shell-exec / side-question / custom-command handlers for BaseUI."""

    def __init__(self, base_ui: "BaseUI") -> None:
        self._base_ui = base_ui

    # --- exec (shell) -----------------------------------------------------

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
                self._base_ui.message_queue.put_nowait(entry)
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

            # create_subprocess_shell is intentional here: cmd is raw text a
            # human typed into the /exec prompt (pipes, redirects, globs are
            # the point), never assembled from untrusted parts.
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
                    self._base_ui.append_to_output(decoded_line, end="")

            # Fail-fast fan-out: a broken reader should abort immediately, not
            # be masked by return_exceptions.
            await asyncio.gather(
                read_stream(process.stdout),
                read_stream(process.stderr, is_stderr=True),
            )

            return_code = await process.wait()

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
            # Reap the child BEFORE touching the UI: an append_to_output failure
            # during teardown must not skip the cleanup and orphan the process.
            # An un-reaped child at loop close logs
            # "Loop <...> that handles pid N is closed" when it eventually exits.
            if process is not None and process.returncode is None:
                try:
                    process.terminate()
                    await asyncio.wait_for(process.wait(), timeout=1.0)
                except BaseException:
                    # BaseException, not Exception: a second cancel (Ctrl+C
                    # again, or shutdown) landing on the await above would
                    # otherwise skip the kill and leave the process running.
                    try:
                        process.kill()
                    except Exception:
                        # Best-effort kill during teardown; re-raise below regardless.
                        pass
                    try:
                        await asyncio.wait_for(process.wait(), timeout=1.0)
                    except BaseException:
                        pass
            self._base_ui.append_to_output("\n[Cancelled]\n")
            raise  # Re-raise to allow proper task cancellation
        except Exception as e:
            self._base_ui.append_to_output(f"\n[Error: {e}]\n")
        finally:
            self._base_ui.is_thinking = False
            self._base_ui.running_llm_task = None
            await self._base_ui.update_system_info()
            self._base_ui.invalidate_ui()

    # --- /btw side question -----------------------------------------------

    def handle_btw_command(self, text: str) -> bool:
        """Handle /btw <question> — ask a side question without saving to history.

        Intentionally works while the LLM is thinking (no _is_thinking guard).
        Runs as an independent background task to avoid interfering with the
        main conversation.
        """
        text = text.strip()
        for cmd in self._base_ui.btw_commands:
            prefix = f"{cmd} "
            if text.lower().startswith(prefix):
                question = text[len(prefix) :].strip()
                if not question:
                    continue

                async def job(q=question):
                    # Through `self._base_ui` (not bare `self`):
                    # `stream_btw_response` is also a `BaseUI` delegator, and
                    # subclasses (or test
                    # doubles) override it there to stub the network call.
                    await self._base_ui.stream_btw_response(self._base_ui.llm_task, q)

                # Bypass the serializing message queue — run as an independent
                # background task so it executes in parallel with the main LLM.
                task = asyncio.create_task(job())
                self._base_ui.background_tasks.add(task)
                task.add_done_callback(self._base_ui.background_tasks.discard)
                return True
        return False

    async def stream_btw_response(self, llm_task: "LLMTask", question: str):
        """Run an ephemeral LLM query that runs alongside the current conversation.

        Uses a fresh, independent pydantic-ai Agent so there are no race conditions
        with the possibly-running main LLM task (no shared state is mutated).
        The response is never saved to conversation history.
        """
        try:
            timestamp = datetime.now().strftime("%H:%M")
            self._base_ui.append_to_output(f"\n💭 {timestamp} >> {question.strip()}\n")
            self._base_ui.append_to_output(
                stylize_muted("  (side question — not saved to history)\n")
            )

            # Load current history for context (read-only snapshot).
            # Strip SystemPromptPart entries so the main agent's system prompt
            # doesn't conflict with the btw agent's own system prompt.
            # lazy: zrb internal (heavy via transitive)
            # lazy: zrb internal (heavy via transitive)
            from zrb.llm.agent import create_agent
            from zrb.llm.agent.types import ModelRequest, SystemPromptPart

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

            _sys_prompt = (
                llm_task.get_system_prompt(self._base_ui.ctx)
                + "\n\nAnswer the user's question concisely using this information when relevant."
            )
            # The UI's selected model if set (from /model), else CFG's — either
            # way resolved against the configured credentials, since `/model`
            # stores the name the user typed.
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
                resolve_model=False,  # already resolved above
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
            self._base_ui.append_to_output(f"\n[Error: {e}]\n")
        finally:
            self._base_ui.invalidate_ui()

    # --- custom commands --------------------------------------------------

    def handle_custom_command(self, text: str) -> bool:
        if self._base_ui.is_thinking:
            return False

        text = text.strip()
        if not text:
            return False

        prompt = resolve_custom_command(text, self._base_ui.custom_commands)
        if prompt is not None:
            self._base_ui.submit_message(prompt)
            return True
        return False
