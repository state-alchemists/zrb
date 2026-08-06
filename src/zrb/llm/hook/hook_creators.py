import asyncio
import json
import logging
import os
import selectors
import signal
import subprocess
import threading
from typing import Any, Callable

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

# How long _read_hook_output blocks in one selector poll. Also the extra latency
# it costs a hook whose descendants hold the pipes open past the child's exit:
# one quiet interval is what proves nothing more is coming.
_HOOK_DRAIN_INTERVAL = 0.05

# Bounded so a large stdin payload cannot monopolize the loop between polls.
_PIPE_WRITE_CHUNK = 32768


def create_command_hook(
    config: CommandHookConfig, timeout: float | None = None
) -> HookCallable:
    async def command_hook(context: HookContext) -> HookResult:
        env = os.environ.copy()

        env["CLAUDE_HOOK_EVENT"] = str(context.event.value)
        env["CLAUDE_HOOK_EVENT_NAME"] = context.hook_event_name or str(
            context.event.value
        )
        env["CLAUDE_CWD"] = context.cwd or ""
        env["CLAUDE_TRANSCRIPT_PATH"] = context.transcript_path or ""
        env["CLAUDE_PERMISSION_MODE"] = context.permission_mode

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

        try:
            # Try to serialize event_data, fall back to string representation
            if context.event_data is not None:
                _set_bounded_env("CLAUDE_EVENT_DATA", json.dumps(context.event_data))
            else:
                env["CLAUDE_EVENT_DATA"] = "null"
        except (TypeError, ValueError):
            _set_bounded_env("CLAUDE_EVENT_DATA", str(context.event_data))

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
            process = await _run_detached(
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
                name="zrb-hook-spawn",
            )
            # Read the group NOW, while the child is certainly alive. By timeout
            # time the child may be a zombie or reaped, and getpgid then fails
            # with ESRCH — losing the only handle on descendants that outlived
            # it. See _kill_process_tree.
            hook_pgid = _read_process_group(process)
            try:
                stdout, stderr = await asyncio.wait_for(
                    _run_detached(
                        lambda: _read_hook_output(process, stdin_payload),
                        name="zrb-hook-io",
                    ),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                _kill_process_tree(process, hook_pgid)
                # process is a sync subprocess.Popen, so .wait() returns an
                # int — awaiting it raises "'int' object can't be awaited",
                # which previously swallowed this TimeoutError and left the
                # subprocess unreaped. Reap off-thread instead.
                await _run_detached(process.wait, name="zrb-hook-reap")
                logger.warning(
                    f"Command hook timed out after {timeout}s and was killed: "
                    f"{config.command[:60]}"
                )
                return HookResult(
                    success=False,
                    output=f"Command hook timed out after {timeout}s",
                )
            except asyncio.CancelledError:
                _kill_process_tree(process, hook_pgid)
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


def _read_hook_output(
    process: subprocess.Popen, stdin_payload: bytes
) -> tuple[bytes, bytes]:
    """Feed stdin and collect stdout/stderr, returning once the *child* exits.

    ``Popen.communicate`` returns at pipe **EOF**, which is not the same event.
    A hook that backgrounds work and returns immediately — ``cmd & disown``, the
    shape Claude-Code notifiers use — leaves a descendant holding the inherited
    write ends, so EOF never comes: a hook that *succeeded* in milliseconds gets
    reported as a timeout, every single firing. The child's own exit is the
    event that actually decides the hook, and everything the child wrote is in
    the pipe buffer by the time it exits, so nothing of its output is lost.

    Output a *descendant* writes after the parent exits is dropped. That output
    could never have been used: the hook's result is already decided.

    Draining runs throughout rather than only after exit. A hook writing more
    than one pipe buffer (~64 KiB) blocks in ``write`` until someone reads, so
    "wait, then read" would deadlock exactly the hooks with the most to say.

    POSIX only. The Windows selector cannot poll pipes and its fds have no
    non-blocking mode, so Windows keeps ``communicate`` — where a leaked
    descendant is instead handled by the psutil child walk in
    ``_kill_process_tree``.
    """
    if os.name != "posix":
        return process.communicate(input=stdin_payload)

    sel = selectors.DefaultSelector()
    collected: dict[int, list[bytes]] = {}
    stdout_chunks: list[bytes] = []
    stderr_chunks: list[bytes] = []
    pending = memoryview(stdin_payload)
    try:
        for pipe, chunks in (
            (process.stdout, stdout_chunks),
            (process.stderr, stderr_chunks),
        ):
            if pipe is not None:
                os.set_blocking(pipe.fileno(), False)
                sel.register(pipe, selectors.EVENT_READ)
                collected[pipe.fileno()] = chunks
        if process.stdin is not None:
            if pending:
                os.set_blocking(process.stdin.fileno(), False)
                sel.register(process.stdin, selectors.EVENT_WRITE)
            else:
                _close_pipe(process.stdin)

        while sel.get_map():
            events = sel.select(timeout=_HOOK_DRAIN_INTERVAL)
            had_readable = False
            for key, _ in events:
                if key.fileobj is process.stdin:
                    pending = _write_stdin(sel, process.stdin, pending)
                else:
                    had_readable = True
                    _read_pipe(sel, key, collected[key.fd])
            if process.poll() is None:
                continue
            # The child is gone: stop feeding it, and leave as soon as a full
            # poll interval turns up nothing more to read. Whatever still holds
            # these pipes open is a descendant that outlived it.
            if process.stdin is not None:
                _unregister(sel, process.stdin)
                _close_pipe(process.stdin)
            if not had_readable:
                break
    finally:
        sel.close()
        for pipe in (process.stdin, process.stdout, process.stderr):
            _close_pipe(pipe)
    # communicate() ends with wait(); match it, so returncode is always set for
    # the caller. Only reachable via EOF-before-exit, where the child is already
    # on its way out — and the caller's wait_for still bounds it.
    if process.poll() is None:
        process.wait()
    return b"".join(stdout_chunks), b"".join(stderr_chunks)


def _read_pipe(sel: "selectors.BaseSelector", key: Any, chunks: list[bytes]) -> None:
    """Drain one ready pipe; unregister and close it at EOF."""
    try:
        data = os.read(key.fd, 32768)
    except BlockingIOError:
        return
    except OSError:
        data = b""
    if data:
        chunks.append(data)
        return
    _unregister(sel, key.fileobj)
    _close_pipe(key.fileobj)


def _write_stdin(
    sel: "selectors.BaseSelector", stdin: Any, pending: memoryview
) -> memoryview:
    """Write what fits of *pending*; close stdin once it is fully delivered."""
    try:
        written = os.write(stdin.fileno(), pending[:_PIPE_WRITE_CHUNK])
    except BlockingIOError:
        return pending
    except (OSError, ValueError):
        # Broken pipe (child gone or never read stdin) or an already-closed fd.
        _unregister(sel, stdin)
        _close_pipe(stdin)
        return memoryview(b"")
    pending = pending[written:]
    if not pending:
        _unregister(sel, stdin)
        _close_pipe(stdin)
    return pending


def _unregister(sel: "selectors.BaseSelector", fileobj: Any) -> None:
    """Drop *fileobj* from the selector, tolerating an already-dropped one."""
    try:
        sel.unregister(fileobj)
    except (KeyError, ValueError):
        pass


def _close_pipe(pipe: Any) -> None:
    """Close a pipe, tolerating one already closed or never opened."""
    if pipe is None:
        return
    try:
        pipe.close()
    except Exception:
        pass


async def _run_detached(func: Callable[[], Any], name: str) -> Any:
    """Await *func* running on a daemon thread.

    Deliberately **not** ``loop.run_in_executor(None, ...)``. A hook whose
    descendants outlive the kill keeps ``communicate()`` blocked in whatever
    thread runs it — an uncancellable block, since neither ``wait_for`` nor
    Ctrl+C can interrupt a thread mid-syscall. On the default executor that
    costs twice:

    1. The pinned thread is one of a pool the whole of zrb shares, so enough
       timed-out hooks starve unrelated ``run_in_executor``/``to_thread`` work.
    2. ``ThreadPoolExecutor`` workers are non-daemon and joined at interpreter
       exit by ``concurrent.futures.thread._python_exit``, so a single pinned
       hook thread hangs shutdown until its descendants happen to exit —
       surfacing as a ``KeyboardInterrupt`` traceback out of ``t.join()`` when
       the user hits Ctrl+C again to escape it.

    A daemon thread is exempt from both: private to this call, and not joined
    by ``threading._shutdown``. An abandoned one dies with the process.
    """
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    def _settle(setter: Callable[[Any], None], value: Any) -> None:
        # The awaiting side may already be gone: wait_for cancels the future on
        # timeout, and setting a result on a cancelled future raises.
        if not future.done():
            setter(value)

    def _post(setter: Callable[[Any], None], value: Any) -> None:
        try:
            loop.call_soon_threadsafe(_settle, setter, value)
        except RuntimeError:
            # Loop already closed — nobody is waiting on this result.
            pass

    def _runner() -> None:
        try:
            result = func()
        except BaseException as e:
            _post(future.set_exception, e)
        else:
            _post(future.set_result, result)

    threading.Thread(target=_runner, name=name, daemon=True).start()
    return await future


def _read_process_group(process: subprocess.Popen) -> int | None:
    """The process group of a *live* child, or None if it cannot be read.

    Called right after spawn, because the answer is unavailable later: once the
    child exits, ``getpgid`` raises ESRCH even while its group still holds live
    descendants. Never raises — a missing group only costs the group kill, and
    the per-pid fallback still runs.
    """
    pid = getattr(process, "pid", None)
    if not isinstance(pid, int) or not hasattr(os, "getpgid"):
        return None
    try:
        return os.getpgid(pid)
    except Exception as e:
        logger.debug(f"could not read process group for hook pid {pid}: {e}")
        return None


def _kill_process_tree(process: subprocess.Popen, pgid: int | None = None) -> None:
    """Kill a hook subprocess *and its descendants*.

    ``process.kill()`` alone only kills the shell spawned by ``shell=True``.
    A grandchild (``sh -c "sleep 30"`` where the shell forks rather than execs)
    survives it, and — because it inherited the stdout/stderr pipe write ends —
    keeps ``communicate()`` blocked in its worker thread until the grandchild
    exits on its own. The hook returns its timeout result, but the thread stays
    pinned.

    POSIX: signal the process group. Elsewhere, or if the group is already gone,
    fall back to psutil's recursive child walk.

    *pgid* must be the group captured at spawn time (``_read_process_group``).
    Looking it up here instead does not work in the case that matters most: a
    shell that backgrounds a child and exits immediately (``cmd & disown``)
    is already gone by the timeout, so ``getpgid`` raises ESRCH and the group
    kill is skipped — while the backgrounded descendant lives on holding the
    pipes. Only the group survives the leader, so only a group captured while
    the leader lived can reach it.

    Both tree kills are aimed by id, so both are catastrophic if handed one that
    is not a child's: ``killpg`` on our own group, or ``kill_pid`` on our own
    pid, SIGKILLs the running process. ``start_new_session=True`` on the Popen
    is what makes the group distinct — but this verifies it rather than trusting
    it, and skips any kill aimed at us.

    Never raises. This runs on the timeout and cancellation paths, where an
    escaping error would be swallowed by the outer handler — turning a
    ``CancelledError`` that must propagate into an ordinary failed HookResult.
    """
    pid = _safe_tree_kill_pid(process)
    if pgid is None:
        pgid = _read_process_group(process)
    group = _safe_tree_kill_group(pgid)
    group_killed = False
    if group is not None and hasattr(os, "killpg"):
        try:
            os.killpg(group, signal.SIGKILL)
            group_killed = True
        except Exception as e:
            logger.debug(f"killpg failed for hook group {group}: {e}")
    if pid is not None and not group_killed:
        try:
            # lazy: circular — command → ... → hook_creators; also keeps psutil
            # off the import path for the common (non-timeout) case. Inside the
            # try: an ImportError here would escape a function documented never
            # to raise, and the outer handler would swallow the CancelledError
            # that must propagate.
            from zrb.util.cmd.command import kill_pid

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
    """The pid to aim the per-process (psutil) tree kill at, or None if unsafe.

    Returns None for a missing pid, our own pid, or a pid sharing our process
    group — each of which would make ``kill_pid`` SIGKILL this process.
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
        # per-process fallback is still safe, the group kill is guarded
        # separately by _safe_tree_kill_group.
        logger.debug(f"could not read process group for hook pid {pid}: {e}")
    return pid


def _safe_tree_kill_group(pgid: int | None) -> int | None:
    """The process group to ``killpg``, or None when doing so would kill us.

    A group captured at spawn time is not self-evidently someone else's: if
    ``start_new_session`` ever stopped taking effect, the child would share our
    group and the group kill would SIGKILL zrb. Checked against our *current*
    group, which needs no lookup on the (possibly dead) child.
    """
    if pgid is None:
        return None
    if not hasattr(os, "getpgid"):
        return None
    try:
        if pgid == os.getpgid(0):
            logger.debug(
                f"refusing group kill: hook group {pgid} is the current process "
                "group — is start_new_session still set on the hook Popen?"
            )
            return None
    except Exception as e:
        # Cannot read our own group: refuse rather than guess.
        logger.debug(f"could not read the current process group: {e}")
        return None
    return pgid


def create_prompt_hook(config: PromptHookConfig) -> HookCallable:
    async def prompt_hook(context: HookContext) -> HookResult:
        """
        Execute a prompt hook using the LLM system.
        This runs an LLM with the given prompt template and returns the result.
        """
        try:
            # lazy: heavy third-party
            from pydantic_ai import Agent

            model_name = config.model or CFG.LLM_MODEL
            if not model_name:
                logger.error("No LLM model configured for prompt hook")
                return HookResult(success=False, output="No LLM model configured")

            final_model = llm_config.resolve_model(model_name)

            agent = Agent(
                model=final_model,
                system_prompt=config.system_prompt or "",
                deps_type=dict,
            )

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

            result = await agent.run(user_prompt, deps={})

            modifications = {}
            # str() is kept outside the try so the narrowed JSONDecodeError
            # catch covers exactly the json.loads call and nothing else.
            output_text = str(result.output)
            try:
                if output_text.strip().startswith("{") and output_text.strip().endswith(
                    "}"
                ):
                    parsed = json.loads(output_text)
                    if isinstance(parsed, dict):
                        modifications = parsed
            except json.JSONDecodeError:
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
            # lazy: heavy third-party
            from pydantic_ai import Agent

            model_name = config.model or CFG.LLM_MODEL
            if not model_name:
                logger.error("No LLM model configured for agent hook")
                return HookResult(success=False, output="No LLM model configured")

            final_model = llm_config.resolve_model(model_name)

            agent = Agent(
                model=final_model,
                system_prompt=config.system_prompt,
                deps_type=dict,
            )

            # TODO: Add tools from config.tools
            # For now, run without tools

            user_input = ""
            if context.event_data:
                user_input = str(context.event_data)
            elif hasattr(context, "prompt") and context.prompt:
                user_input = context.prompt
            else:
                user_input = f"Hook event: {context.event.value}"

            result = await agent.run(user_input, deps={})

            modifications = {}
            # str() is kept outside the try so the narrowed JSONDecodeError
            # catch covers exactly the json.loads call and nothing else.
            output_text = str(result.output)
            try:
                if output_text.strip().startswith("{") and output_text.strip().endswith(
                    "}"
                ):
                    parsed = json.loads(output_text)
                    if isinstance(parsed, dict):
                        modifications = parsed
            except json.JSONDecodeError:
                pass

            return HookResult(
                success=True, output=str(result.output), modifications=modifications
            )

        except Exception as e:
            logger.error(f"Error executing agent hook: {e}", exc_info=True)
            return HookResult(success=False, output=str(e))

    return agent_hook
