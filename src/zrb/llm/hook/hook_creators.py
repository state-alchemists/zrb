import asyncio
import json
import logging
import os
import signal
import subprocess

from zrb.config.config import CFG
from zrb.llm.config.config import llm_config
from zrb.llm.hook.interface import HookCallable, HookContext, HookResult
from zrb.llm.hook.schema import AgentHookConfig, CommandHookConfig, PromptHookConfig
from zrb.llm.hook.types import HookEvent

logger = logging.getLogger(__name__)

# Events for which Claude Code injects a command hook's plain stdout into the
# model context. For these, when a hook emits unstructured text (not the JSON
# control protocol), we treat that text as additionalContext so a simple
# `echo "..."` hook behaves the same as in Claude Code.
_STDOUT_CONTEXT_EVENTS = frozenset(
    {HookEvent.SESSION_START, HookEvent.USER_PROMPT_SUBMIT}
)

# Per-value cap for injected CLAUDE_* env vars. The OS rejects an exec whose
# combined args+environment exceed ARG_MAX (and a single var over MAX_ARG_STRLEN,
# ~128 KiB). event_data can carry the whole message history, so we cap well
# under that; the full payload is always available on stdin.
_MAX_HOOK_ENV_BYTES = 16384


def create_command_hook(
    config: CommandHookConfig, timeout: float | None = None
) -> HookCallable:
    async def command_hook(context: HookContext) -> HookResult:
        # Prepare environment with Claude Code context variables
        env = os.environ.copy()

        # Inject Claude Code context variables for hook scripts
        env["CLAUDE_HOOK_EVENT"] = str(context.event.value)
        env["CLAUDE_HOOK_EVENT_NAME"] = context.hook_event_name or str(
            context.event.value
        )
        env["CLAUDE_CWD"] = context.cwd or ""
        env["CLAUDE_TRANSCRIPT_PATH"] = context.transcript_path or ""
        env["CLAUDE_PERMISSION_MODE"] = context.permission_mode

        # Phase 7: Environment Variables
        env["CLAUDE_PROJECT_DIR"] = (
            context.cwd or os.getcwd()
        )  # Best guess for project root
        env["CLAUDE_PLUGIN_ROOT"] = ""  # TODO: Need to pass this context if available
        env["CLAUDE_CODE_REMOTE"] = "false"  # Zrb is typically local for now
        if context.metadata.get("remote"):
            env["CLAUDE_CODE_REMOTE"] = "true"

        # Inject context as env vars, but bound each value's size. event_data
        # for SessionStart/Stop/SessionEnd carries the whole message history;
        # serialized into the environment that overflows the OS exec arg+env
        # limit (E2BIG: "Argument list too long"). Hooks get the full structured
        # payload on stdin, so oversized env values are safe to drop.
        def _set_bounded_env(key: str, value: str) -> None:
            if len(value) <= _MAX_HOOK_ENV_BYTES:
                env[key] = value
            # else: omit — the stdin payload carries the data.

        # Inject event-specific data as JSON
        try:
            # Try to serialize event_data, fall back to string representation
            if context.event_data is not None:
                _set_bounded_env("CLAUDE_EVENT_DATA", json.dumps(context.event_data))
            else:
                env["CLAUDE_EVENT_DATA"] = "null"
        except (TypeError, ValueError):
            # If not JSON serializable, use string representation
            _set_bounded_env("CLAUDE_EVENT_DATA", str(context.event_data))

        # Add context fields to environment
        for field in [
            "tool_name",
            "tool_input",
            "prompt",
            "command_name",
            "command_args",
            "command_handled",
            "message",
            "title",
            "notification_type",
            "agent_id",
            "teammate_name",
            "task_id",
        ]:
            value = getattr(context, field, None)
            if value is not None:
                if isinstance(value, dict):
                    _set_bounded_env(f"CLAUDE_{field.upper()}", json.dumps(value))
                else:
                    _set_bounded_env(f"CLAUDE_{field.upper()}", str(value))

        # Claude-Code-compatible hooks read their event payload from stdin as
        # JSON (e.g. peon-ping does `json.load(sys.stdin)["hook_event_name"]`)
        # and ignore the env vars entirely. Feed them the same Claude-shaped
        # payload on stdin so those hooks fire; the env vars above remain for
        # hooks that prefer them.
        claude_payload = context.to_claude_json()
        try:
            stdin_payload = json.dumps(claude_payload).encode()
        except (TypeError, ValueError):
            # Tool args/results may carry non-serializable objects. Fall back to
            # a minimal payload so stdin-driven hooks can still route on event.
            stdin_payload = json.dumps(
                {"hook_event_name": claude_payload.get("hook_event_name")}
            ).encode()

        # Resolve the working directory defensively. A hook must not fail just
        # because the cwd carries a "~" (the OS does not expand it, unlike a
        # shell) or no longer exists — that turned every UI-fired hook into a
        # `[Errno 2] No such file or directory: '~/...'` once the cwd came from
        # a display-formatted path. Expand "~" and fall back to inheriting our
        # own cwd when the target is missing.
        raw_cwd = config.working_dir or context.cwd
        hook_cwd = None
        if raw_cwd:
            expanded = os.path.expanduser(raw_cwd)
            if os.path.isdir(expanded):
                hook_cwd = expanded

        try:
            # Run command with timeout.
            #
            # Use subprocess.Popen in a thread executor instead of
            # asyncio.create_subprocess_shell.  The asyncio subprocess API
            # creates transport/protocol pairs via _make_subprocess_transport
            # / _connect_pipes, which can leave _pipes entries as None if
            # cancelled mid-init.  _try_finish then skips _call_connection_lost
            # and _wait() hangs forever (CPython bug).  A plain subprocess.Popen
            # has no asyncio transport objects, so task cancellation cannot
            # trigger that hang path.
            loop = asyncio.get_running_loop()
            process = await loop.run_in_executor(
                None,
                lambda: subprocess.Popen(
                    config.command,
                    shell=True,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=hook_cwd,
                    env=env,
                    # Own session/process group so the whole tree can be killed
                    # on timeout — see _kill_process_tree. POSIX-only; silently
                    # ignored on Windows, where psutil handles the children.
                    start_new_session=True,
                ),
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    loop.run_in_executor(
                        None, lambda: process.communicate(input=stdin_payload)
                    ),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                _kill_process_tree(process)
                # process is a sync subprocess.Popen, so .wait() returns an
                # int — awaiting it raises "'int' object can't be awaited",
                # which previously swallowed this TimeoutError and left the
                # subprocess unreaped. Reap in the executor instead.
                await loop.run_in_executor(None, process.wait)
                logger.warning(
                    f"Command hook timed out after {timeout}s and was killed: "
                    f"{config.command[:60]}"
                )
                return HookResult(
                    success=False,
                    output=f"Command hook timed out after {timeout}s",
                )
            except asyncio.CancelledError:
                _kill_process_tree(process)
                raise

            output = stdout.decode().strip()
            stderr_output = stderr.decode().strip()

            # Claude Code compatibility: exit code 2 means block, 0 means success
            # Other non-zero exit codes are errors
            exit_code = process.returncode

            if exit_code == 2:
                # Blocking decision. Claude Code feeds the block reason back from
                # STDERR on exit 2; zrb historically read it from stdout. Accept
                # both, in this precedence: an explicit `reason` in a stdout JSON
                # control object > stderr (the Claude convention) > plain stdout
                # text > a default. This keeps existing stdout-based hooks working
                # while making a Claude-style `echo "reason" >&2; exit 2` carry its
                # reason instead of silently falling back to the default.
                modifications = {}
                json_reason: str | None = None
                stdout_is_json = False

                try:
                    data = json.loads(output)
                    if isinstance(data, dict):
                        # Claude Code format: {"decision": "block", "reason": "...", ...}
                        modifications = data
                        stdout_is_json = True
                        json_reason = data.get("reason")
                except Exception:
                    # Not JSON; the plain-stdout fallback below handles it.
                    pass

                # Only treat stdout as the reason when it was NOT a JSON control
                # object (a JSON object without a reason key keeps the default).
                plain_stdout = None if stdout_is_json else (output or None)
                reason = (
                    json_reason or stderr_output or plain_stdout or "Blocked by hook"
                )

                # Merge provided modifications with blocking modifications
                blocking_modifications = {
                    "decision": "block",
                    "reason": reason,
                    "exit_code": 2,
                }
                blocking_modifications.update(modifications)
                return HookResult(
                    success=False,
                    output=output,  # Include output for logging/debugging
                    should_stop=True,
                    modifications=blocking_modifications,
                )

            elif exit_code == 0:
                # Success - parse output for modifications
                modifications = {}
                try:
                    data = json.loads(output)
                    if isinstance(data, dict):
                        modifications = data
                except json.JSONDecodeError:
                    # Not JSON, treat as plain output
                    pass

                # Claude-compatible stdout-as-context: for SessionStart /
                # UserPromptSubmit, unstructured stdout (the hook did not use the
                # JSON control protocol) is injected as additionalContext. When the
                # hook DID emit a JSON object we respect it verbatim — it may carry
                # its own additionalContext or a decision — and do not override.
                if (
                    output
                    and not modifications
                    and context.event in _STDOUT_CONTEXT_EVENTS
                ):
                    modifications = {"additionalContext": output}

                return HookResult(
                    success=True, output=output, modifications=modifications
                )
            elif exit_code is not None and exit_code < 0:
                # Negative return code: the child was killed by a signal
                # (POSIX reports -N for signal N). This is almost always the
                # terminal delivering SIGINT (-2, Ctrl+C) or SIGTERM (-15) to
                # the whole process group during interrupt/teardown — not a
                # hook bug. Treat it as a quiet non-failure so a normal Ctrl+C
                # does not emit a scary "Command hook failed" error.
                sig_num = -exit_code
                try:
                    sig_name = signal.Signals(sig_num).name
                except ValueError:
                    sig_name = f"signal {sig_num}"
                logger.debug(
                    f"Command hook interrupted by {sig_name}: " f"{config.command[:60]}"
                )
                return HookResult(
                    success=False,
                    output=f"Command hook interrupted by {sig_name}",
                )
            else:
                # Error case
                error_msg = f"Command failed with exit code {exit_code}"
                if stderr_output:
                    error_msg += f": {stderr_output}"
                elif output:
                    error_msg += f": {output}"

                logger.error(f"Command hook failed: {error_msg}")
                return HookResult(success=False, output=error_msg)

        except Exception as e:
            logger.error(f"Error executing command hook: {e}")
            return HookResult(success=False, output=str(e))

    return command_hook


def _kill_process_tree(process: subprocess.Popen) -> None:
    """Kill a hook subprocess *and its descendants*.

    ``process.kill()`` alone only kills the shell spawned by ``shell=True``.
    A grandchild (``sh -c "sleep 30"`` where the shell forks rather than execs)
    survives it, and — because it inherited the stdout/stderr pipe write ends —
    keeps ``communicate()`` blocked in its worker thread until the grandchild
    exits on its own. The hook returns its timeout result, but the thread stays
    pinned: enough timed-out hooks and the pool has no free workers left.

    POSIX: signal the process group. Elsewhere, or if the group is already gone,
    fall back to psutil's recursive child walk.

    Both tree kills are aimed by pid, so both are catastrophic if handed a pid
    that is not a child: ``killpg`` on our own group, or ``kill_pid`` on our own
    pid, SIGKILLs the running process. ``start_new_session=True`` on the Popen
    is what makes the group distinct — but this verifies it rather than trusting it, and
    skips *both* tree kills for a pid that is or shares us.

    Never raises. This runs on the timeout and cancellation paths, where an
    escaping error would be swallowed by the outer handler — turning a
    ``CancelledError`` that must propagate into an ordinary failed HookResult.
    """
    pid = _safe_tree_kill_pid(process)
    group_killed = False
    if pid is not None and hasattr(os, "killpg"):
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
            group_killed = True
        except Exception as e:
            logger.debug(f"killpg failed for hook pid {pid}: {e}")
    if pid is not None and not group_killed:
        # lazy: circular — command → ... → hook_creators; also keeps psutil off
        # the import path for the common (non-timeout) case.
        from zrb.util.cmd.command import kill_pid

        try:
            kill_pid(pid, print_method=logger.debug)
        except Exception as e:
            logger.debug(f"Failed to kill hook process tree {pid}: {e}")
    # Always signal the direct child too: it is the only handle that exists on
    # Windows, and the last resort if both tree kills failed. Safe regardless of
    # the checks above — Popen.kill only ever targets its own child.
    try:
        process.kill()
    except Exception as e:
        logger.debug(f"Failed to kill hook process: {e}")


def _safe_tree_kill_pid(process: subprocess.Popen) -> int | None:
    """The pid to aim a tree kill at, or None when no tree kill is safe.

    Returns None for a missing pid, our own pid, or a pid sharing our process
    group — each of which would make ``killpg``/``kill_pid`` SIGKILL this process.
    """
    pid = getattr(process, "pid", None)
    if not isinstance(pid, int):
        return None
    if pid == os.getpid():
        logger.debug(f"refusing tree kill: hook pid {pid} is the current process")
        return None
    try:
        if hasattr(os, "getpgid") and os.getpgid(pid) == os.getpgid(0):
            logger.debug(
                f"refusing tree kill: hook pid {pid} shares the current process "
                "group — is start_new_session still set on the hook Popen?"
            )
            return None
    except Exception as e:
        # Cannot determine the group (already reaped, or no getpgid): the
        # per-process fallback below is still safe, the group kill is not.
        logger.debug(f"could not read process group for hook pid {pid}: {e}")
    return pid


def create_prompt_hook(config: PromptHookConfig) -> HookCallable:
    async def prompt_hook(context: HookContext) -> HookResult:
        """
        Execute a prompt hook using the LLM system.
        This runs an LLM with the given prompt template and returns the result.
        """
        try:
            # Import here to avoid circular imports
            # lazy: heavy third-party
            from pydantic_ai import Agent

            # Get LLM configuration
            model_name = config.model or CFG.LLM_MODEL
            if not model_name:
                logger.error("No LLM model configured for prompt hook")
                return HookResult(success=False, output="No LLM model configured")

            final_model = llm_config.resolve_model(model_name)

            # Create agent with the prompt
            agent = Agent(
                model=final_model,
                system_prompt=config.system_prompt or "",
                deps_type=dict,
            )

            # Format user prompt template with context
            # Simple template substitution using context fields
            user_prompt = config.user_prompt_template
            for field_name in dir(context):
                if not field_name.startswith("_"):
                    field_value = getattr(context, field_name)
                    if isinstance(field_value, (str, int, float, bool)):
                        placeholder = f"{{{{{field_name}}}}}"
                        if placeholder in user_prompt:
                            user_prompt = user_prompt.replace(
                                placeholder, str(field_value)
                            )

            # Run the agent
            result = await agent.run(user_prompt, deps={})

            # Parse the result for modifications
            modifications = {}
            # str() is kept outside the try so the narrowed JSONDecodeError
            # catch covers exactly the json.loads call and nothing else.
            output_text = str(result.output)
            try:
                # Try to parse as JSON if it looks like JSON
                if output_text.strip().startswith("{") and output_text.strip().endswith(
                    "}"
                ):
                    parsed = json.loads(output_text)
                    if isinstance(parsed, dict):
                        modifications = parsed
            except json.JSONDecodeError:
                # Not JSON, use as plain output
                pass

            return HookResult(
                success=True, output=str(result.output), modifications=modifications
            )

        except Exception as e:
            logger.error(f"Error executing prompt hook: {e}", exc_info=True)
            return HookResult(success=False, output=str(e))

    return prompt_hook


def create_agent_hook(config: AgentHookConfig) -> HookCallable:
    async def agent_hook(context: HookContext) -> HookResult:
        """
        Execute an agent hook with tools.
        This creates an agent with the given system prompt and tools.
        """
        try:
            # Import here to avoid circular imports
            # lazy: heavy third-party
            from pydantic_ai import Agent

            # Get LLM configuration
            model_name = config.model or CFG.LLM_MODEL
            if not model_name:
                logger.error("No LLM model configured for agent hook")
                return HookResult(success=False, output="No LLM model configured")

            final_model = llm_config.resolve_model(model_name)

            # Create agent with system prompt
            agent = Agent(
                model=final_model,
                system_prompt=config.system_prompt,
                deps_type=dict,
            )

            # TODO: Add tools from config.tools
            # For now, run without tools

            # Create a prompt from context
            # Use event_data or other context fields as input
            user_input = ""
            if context.event_data:
                if isinstance(context.event_data, dict):
                    user_input = str(context.event_data)
                else:
                    user_input = str(context.event_data)
            elif hasattr(context, "prompt") and context.prompt:
                user_input = context.prompt
            else:
                user_input = f"Hook event: {context.event.value}"

            # Run the agent
            result = await agent.run(user_input, deps={})

            # Parse the result for modifications
            modifications = {}
            # str() is kept outside the try so the narrowed JSONDecodeError
            # catch covers exactly the json.loads call and nothing else.
            output_text = str(result.output)
            try:
                # Try to parse as JSON if it looks like JSON
                if output_text.strip().startswith("{") and output_text.strip().endswith(
                    "}"
                ):
                    parsed = json.loads(output_text)
                    if isinstance(parsed, dict):
                        modifications = parsed
            except json.JSONDecodeError:
                # Not JSON, use as plain output
                pass

            return HookResult(
                success=True, output=str(result.output), modifications=modifications
            )

        except Exception as e:
            logger.error(f"Error executing agent hook: {e}", exc_info=True)
            return HookResult(success=False, output=str(e))

    return agent_hook
