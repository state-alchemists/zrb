"""The three hook-type factories: command, prompt, and agent.

Each turns a `*HookConfig` into a `HookCallable` that `zrb.llm.hook.manager`
invokes. The subprocess machinery a command hook needs lives in the siblings
`zrb.llm.hook.process_io` (pipes, threads) and `zrb.llm.hook.process_kill`
(tree kills).

For the public hook authoring guide (formats, events, examples), see:
  docs/advanced-topics/hooks.md
"""

import asyncio
import json
import logging
import os
import signal
import subprocess

from zrb.config.config import CFG
from zrb.llm.config.config import llm_config
from zrb.llm.hook.interface import HookCallable, HookContext, HookResult
from zrb.llm.hook.process_io import read_hook_output, run_detached
from zrb.llm.hook.process_kill import kill_process_tree, read_process_group
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

# Context fields exported as CLAUDE_<FIELD>, for hooks that read the environment
# rather than the stdin payload.
_ENV_CONTEXT_FIELDS = (
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
)


def create_command_hook(
    config: CommandHookConfig, timeout: float | None = None
) -> HookCallable:
    async def command_hook(context: HookContext) -> HookResult:
        env = _build_hook_env(context)
        stdin_payload = _encode_stdin_payload(context)
        hook_cwd = _resolve_hook_cwd(config, context)
        try:
            # Use subprocess.Popen in a thread executor instead of
            # asyncio.create_subprocess_shell.  The asyncio subprocess API
            # creates transport/protocol pairs via _make_subprocess_transport
            # / _connect_pipes, which can leave _pipes entries as None if
            # cancelled mid-init.  _try_finish then skips _call_connection_lost
            # and _wait() hangs forever (CPython bug).  A plain subprocess.Popen
            # has no asyncio transport objects, so task cancellation cannot
            # trigger that hang path.
            process = await run_detached(
                lambda: subprocess.Popen(
                    config.command,
                    shell=True,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=hook_cwd,
                    env=env,
                    # Own session/process group so the whole tree can be killed
                    # on timeout — see process_kill.kill_process_tree. POSIX-only;
                    # silently ignored on Windows, where psutil handles children.
                    start_new_session=True,
                ),
                name="zrb-hook-spawn",
            )
            # Read the group NOW, while the child is certainly alive. By timeout
            # time the child may be a zombie or reaped, and getpgid then fails
            # with ESRCH — losing the only handle on descendants that outlived
            # it. See process_kill.kill_process_tree.
            hook_pgid = read_process_group(process)
            try:
                stdout, stderr = await asyncio.wait_for(
                    run_detached(
                        lambda: read_hook_output(process, stdin_payload),
                        name="zrb-hook-io",
                    ),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                kill_process_tree(process, hook_pgid)
                # process is a sync subprocess.Popen, so .wait() returns an
                # int — awaiting it raises "'int' object can't be awaited",
                # which would swallow this TimeoutError and leave the subprocess
                # unreaped. Reap off-thread instead.
                await run_detached(process.wait, name="zrb-hook-reap")
                logger.warning(
                    f"Command hook timed out after {timeout}s and was killed: "
                    f"{config.command[:60]}"
                )
                return HookResult(
                    success=False,
                    output=f"Command hook timed out after {timeout}s",
                )
            except asyncio.CancelledError:
                kill_process_tree(process, hook_pgid)
                raise

            return _interpret_exit(
                exit_code=process.returncode,
                output=stdout.decode().strip(),
                stderr_output=stderr.decode().strip(),
                context=context,
                command=config.command,
            )

        except Exception as e:
            logger.error(f"Error executing command hook: {e}")
            return HookResult(success=False, output=str(e))

    return command_hook


def _build_hook_env(context: HookContext) -> dict[str, str]:
    """The child's environment: the ``CLAUDE_*`` view of *context*.

    Values are size-bounded. event_data for SessionStart/Stop/SessionEnd carries
    the whole message history; serialized into the environment that overflows
    the OS exec arg+env limit (E2BIG: "Argument list too long"). Hooks get the
    full structured payload on stdin, so dropping an oversized env value is safe.
    """
    env = os.environ.copy()
    env["CLAUDE_HOOK_EVENT"] = str(context.event.value)
    env["CLAUDE_HOOK_EVENT_NAME"] = context.hook_event_name or str(context.event.value)
    env["CLAUDE_CWD"] = context.cwd or ""
    env["CLAUDE_TRANSCRIPT_PATH"] = context.transcript_path or ""
    env["CLAUDE_PERMISSION_MODE"] = context.permission_mode
    # Best guess for project root
    env["CLAUDE_PROJECT_DIR"] = context.cwd or os.getcwd()
    env["CLAUDE_PLUGIN_ROOT"] = ""  # TODO: Need to pass this context if available
    env["CLAUDE_CODE_REMOTE"] = "true" if context.metadata.get("remote") else "false"
    try:
        # Try to serialize event_data, fall back to string representation
        if context.event_data is not None:
            _set_bounded_env(env, "CLAUDE_EVENT_DATA", json.dumps(context.event_data))
        else:
            env["CLAUDE_EVENT_DATA"] = "null"
    except (TypeError, ValueError):
        _set_bounded_env(env, "CLAUDE_EVENT_DATA", str(context.event_data))
    for field in _ENV_CONTEXT_FIELDS:
        value = getattr(context, field, None)
        if value is None:
            continue
        encoded = json.dumps(value) if isinstance(value, dict) else str(value)
        _set_bounded_env(env, f"CLAUDE_{field.upper()}", encoded)
    return env


def _set_bounded_env(env: dict[str, str], key: str, value: str) -> None:
    """Set *key* unless it would blow the exec arg+env limit — see _build_hook_env."""
    if len(value) <= _MAX_HOOK_ENV_BYTES:
        env[key] = value


def _encode_stdin_payload(context: HookContext) -> bytes:
    """The Claude-shaped JSON payload fed to the hook on stdin.

    Claude-Code-compatible hooks read their event payload from stdin as JSON
    (e.g. peon-ping does ``json.load(sys.stdin)["hook_event_name"]``) and ignore
    the env vars entirely. Feed them the same payload so those hooks fire; the
    env vars from `_build_hook_env` remain for hooks that prefer them.
    """
    claude_payload = context.to_claude_json()
    try:
        return json.dumps(claude_payload).encode()
    except (TypeError, ValueError):
        # Tool args/results may carry non-serializable objects. Fall back to a
        # minimal payload so stdin-driven hooks can still route on event.
        return json.dumps(
            {"hook_event_name": claude_payload.get("hook_event_name")}
        ).encode()


def _resolve_hook_cwd(config: CommandHookConfig, context: HookContext) -> str | None:
    """The directory to run the hook in, or None to inherit our own.

    Resolved defensively. A hook must not fail just because the cwd carries a
    "~" (the OS does not expand it, unlike a shell) or no longer exists — that
    turned every UI-fired hook into a ``[Errno 2] No such file or directory:
    '~/...'`` once the cwd came from a display-formatted path.
    """
    raw_cwd = config.working_dir or context.cwd
    if not raw_cwd:
        return None
    expanded = os.path.expanduser(raw_cwd)
    return expanded if os.path.isdir(expanded) else None


def _interpret_exit(
    exit_code: int | None,
    output: str,
    stderr_output: str,
    context: HookContext,
    command: str,
) -> HookResult:
    """Turn a finished hook's exit code and streams into a HookResult.

    Claude Code compatibility: exit code 2 means block, 0 means success. Other
    non-zero codes are errors — except a negative one, which is a signal rather
    than a hook bug.
    """
    if exit_code == 2:
        return _blocked_result(output, stderr_output)
    if exit_code == 0:
        return _success_result(output, context)
    if exit_code is not None and exit_code < 0:
        return _signal_result(exit_code, command)
    return _failure_result(exit_code, output, stderr_output)


def _blocked_result(output: str, stderr_output: str) -> HookResult:
    """Exit 2 — the hook blocked the action.

    Claude Code feeds the block reason back from STDERR on exit 2; zrb also
    accepts it on stdout. Precedence: an explicit `reason` in a stdout JSON
    control object > stderr (the Claude convention) > plain stdout text > a
    default. So both a stdout-based hook and a Claude-style
    ``echo "reason" >&2; exit 2`` carry their reason.
    """
    modifications: dict = {}
    stdout_is_json = False
    try:
        # Claude Code format: {"decision": "block", "reason": "...", ...}
        data = json.loads(output)
        if isinstance(data, dict):
            modifications = data
            stdout_is_json = True
    except Exception:
        pass

    # Only treat stdout as the reason when it was NOT a JSON control object (a
    # JSON object without a reason key keeps the default).
    plain_stdout = None if stdout_is_json else (output or None)
    reason = (
        modifications.get("reason")
        or stderr_output
        or plain_stdout
        or "Blocked by hook"
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


def _success_result(output: str, context: HookContext) -> HookResult:
    """Exit 0 — success, with stdout parsed for a JSON control object.

    Claude-compatible stdout-as-context: for SessionStart / UserPromptSubmit,
    unstructured stdout (the hook did not use the JSON control protocol) is
    injected as additionalContext. When the hook DID emit a JSON object we
    respect it verbatim — it may carry its own additionalContext or a decision —
    and do not override.
    """
    modifications: dict = {}
    try:
        data = json.loads(output)
        if isinstance(data, dict):
            modifications = data
    except json.JSONDecodeError:
        # Not JSON, treat as plain output
        pass

    if output and not modifications and context.event in _STDOUT_CONTEXT_EVENTS:
        modifications = {"additionalContext": output}

    return HookResult(success=True, output=output, modifications=modifications)


def _signal_result(exit_code: int, command: str) -> HookResult:
    """A negative return code — the child was killed by a signal.

    POSIX reports -N for signal N. This is almost always the terminal delivering
    SIGINT (-2, Ctrl+C) or SIGTERM (-15) to the whole process group during
    interrupt/teardown — not a hook bug. Treat it as a quiet non-failure so a
    normal Ctrl+C does not emit a scary "Command hook failed" error.
    """
    sig_num = -exit_code
    try:
        sig_name = signal.Signals(sig_num).name
    except ValueError:
        sig_name = f"signal {sig_num}"
    logger.debug(f"Command hook interrupted by {sig_name}: {command[:60]}")
    return HookResult(
        success=False,
        output=f"Command hook interrupted by {sig_name}",
    )


def _failure_result(
    exit_code: int | None, output: str, stderr_output: str
) -> HookResult:
    """Any other non-zero exit — a genuine hook failure."""
    error_msg = f"Command failed with exit code {exit_code}"
    if stderr_output:
        error_msg += f": {stderr_output}"
    elif output:
        error_msg += f": {output}"
    logger.error(f"Command hook failed: {error_msg}")
    return HookResult(success=False, output=error_msg)


def create_prompt_hook(config: PromptHookConfig) -> HookCallable:
    async def prompt_hook(context: HookContext) -> HookResult:
        """Run an LLM with the configured prompt template and return its output."""
        return await _run_llm_hook(
            kind="prompt",
            model=config.model,
            system_prompt=config.system_prompt or "",
            user_prompt=_render_prompt_template(config.user_prompt_template, context),
        )

    return prompt_hook


def _render_prompt_template(template: str, context: HookContext) -> str:
    """Substitute ``{{field}}`` placeholders from *context*'s scalar fields."""
    for field_name in dir(context):
        if field_name.startswith("_"):
            continue
        field_value = getattr(context, field_name)
        if isinstance(field_value, (str, int, float, bool)):
            placeholder = f"{{{{{field_name}}}}}"
            if placeholder in template:
                template = template.replace(placeholder, str(field_value))
    return template


def create_agent_hook(config: AgentHookConfig) -> HookCallable:
    async def agent_hook(context: HookContext) -> HookResult:
        """Run an agent with the configured system prompt over the event payload."""
        # TODO: Add tools from config.tools — for now, run without tools
        return await _run_llm_hook(
            kind="agent",
            model=config.model,
            system_prompt=config.system_prompt,
            user_prompt=_agent_hook_input(context),
        )

    return agent_hook


def _agent_hook_input(context: HookContext) -> str:
    """What to hand the agent as its user turn, best available first."""
    if context.event_data:
        return str(context.event_data)
    if context.prompt:
        return context.prompt
    return f"Hook event: {context.event.value}"


async def _run_llm_hook(
    kind: str, model: str | None, system_prompt: str, user_prompt: str
) -> HookResult:
    """Shared body of the prompt and agent hooks.

    They differ only in where their two prompts come from; *kind* names the one
    in play for log messages.
    """
    try:
        # lazy: pydantic_ai (heavy third-party deferral)
        from pydantic_ai import Agent

        model_name = model or CFG.LLM_MODEL
        if not model_name:
            logger.error(f"No LLM model configured for {kind} hook")
            return HookResult(success=False, output="No LLM model configured")

        agent = Agent(
            model=llm_config.resolve_model(model_name),
            system_prompt=system_prompt,
            deps_type=dict,
        )
        result = await agent.run(user_prompt, deps={})

        output_text = str(result.output)
        return HookResult(
            success=True,
            output=output_text,
            modifications=_parse_json_object(output_text),
        )
    except Exception as e:
        logger.error(f"Error executing {kind} hook: {e}", exc_info=True)
        return HookResult(success=False, output=str(e))


def _parse_json_object(text: str) -> dict:
    """*text* as a dict when it is a JSON object, else an empty dict."""
    stripped = text.strip()
    if not (stripped.startswith("{") and stripped.endswith("}")):
        return {}
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
