from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import Field

from zrb.config.config import CFG
from zrb.llm.agent_activity import HasActivityTracking, agent_activity_registry
from zrb.llm.agent_runner import run_agent
from zrb.llm.agent_state import get_current_ui
from zrb.llm.ambient_state import (
    get_active_worktree,
    get_current_tool_session,
    get_session_ownership_key,
)
from zrb.llm.config.limiter import get_run_llm_limiter
from zrb.llm.delegation_api import (
    SubAgentManagerAPI,
    default_sub_agent_manager,
    get_live_session_registry,
    start_titling,
)
from zrb.llm.hook.manager import get_run_hook_manager
from zrb.llm.hook.types import HookEvent
from zrb.llm.permission import Capability, tag
from zrb.llm.shell_cut import get_run_shell_cut_signal
from zrb.llm.tool.worktree import enter_worktree, exit_worktree
from zrb.llm.ui.buffered_ui import BufferedUI
from zrb.llm.ui_fallback.resolution import resolve_ui

if TYPE_CHECKING:
    from zrb.llm.ui.any_ui import AnyUI

from zrb.llm.util.roster import cap_items, search_roster
from zrb.llm.util.subagent_session_naming import (
    format_delegated_session_name,
    parse_delegated_session,
    subagent_only_directories,
)
from zrb.util.string.name import get_random_name
from zrb.util.string.suggestion import suggest_name


@dataclass
class AgentTaskResult:
    """Result from running a single agent task."""

    agent_name: str
    result: str | None
    error: str | None

    @property
    def success(self) -> bool:
        return self.error is None or self.error == ""


def _format_envelope(
    deliverable: str,
    non_goals: list[str] | str,
    task: str,
    additional_context: str,
) -> str:
    """Assemble the scope-clamped envelope the sub-agent reads first."""
    if isinstance(non_goals, list) and non_goals:
        non_goals_block = "\n".join(f"  - {item}" for item in non_goals)
    elif isinstance(non_goals, str) and non_goals.strip():
        non_goals_block = f"  - {non_goals.strip()}"
    else:
        non_goals_block = "  - (none declared)"
    context_block = additional_context.strip() if additional_context else "(none)"
    active_wt = get_active_worktree()
    if active_wt:
        wt_line = f"Active worktree: {active_wt}"
        context_block = (
            f"{context_block}\n{wt_line}" if context_block != "(none)" else wt_line
        )
    return (
        f"DELIVERABLE: {deliverable}\n"
        f"NON-GOALS (do NOT do these, even if obviously related):\n"
        f"{non_goals_block}\n\n"
        f"TASK: {task}\n\n"
        f"CONTEXT:\n{context_block}\n\n"
        "BEFORE RETURNING: confirm the deliverable exists exactly as stated "
        "and no non-goal was violated. If the work expanded beyond the "
        "deliverable, stop and report what you skipped rather than including it."
    )


async def run_agent_task(
    agent_name: str,
    deliverable: str,
    non_goals: list[str],
    task: str,
    additional_context: str,
    sub_agent_manager: SubAgentManagerAPI,
    ui: AnyUI,
    flush_ui: bool = False,
    yolo: bool | None = None,
) -> AgentTaskResult:
    """Run one sub-agent task. `yolo=None` inherits the parent's setting."""
    sub_agent = sub_agent_manager.create_agent(agent_name, yolo=yolo)
    if not sub_agent:
        return AgentTaskResult(
            agent_name,
            None,
            agent_not_found_message(agent_name, sub_agent_manager),
        )

    full_message = _format_envelope(deliverable, non_goals, task, additional_context)

    agent_id = uuid.uuid4().hex[:8]
    # Per-session scope so the web runner's sessions don't share an activity panel.
    activity_session_id = get_session_ownership_key(get_current_tool_session())
    _tracks_activity = _start_activity_tracking(
        ui, agent_id, agent_name, deliverable or task, activity_session_id
    )
    session = _register_live_session(
        ui,
        activity_session_id,
        agent_id,
        agent_name,
        sub_agent_manager,
        yolo,
        deliverable or task,
    )
    try:
        # Inside the try so a cancel here goes through `consume_cancelled_flag`.
        await fire_subagent_hook(HookEvent.SUBAGENT_START, agent_name, agent_id)
        result, history = await run_agent(
            agent=sub_agent,
            message=full_message,
            message_history=[],
            limiter=get_run_llm_limiter(),
            ui=ui,
            yolo=bool(yolo) if yolo is not None else yolo,
            # Own scope so read-before-overwrite tracking doesn't credit the
            # parent's reads; not agent_id (32-bit, collides). "" mints one.
            run_scope=session.run_scope if session is not None else "",
        )

        result = _finalize_successful_run(
            ui,
            session,
            flush_ui,
            activity_session_id,
            agent_id,
            agent_name,
            history,
            result,
        )
        return AgentTaskResult(agent_name, result, None)

    except asyncio.CancelledError:
        # Esc on this sub-agent's view cancels only its turn; any other
        # cancellation (the main run's own Esc) re-raises.
        if session is not None and session.consume_cancelled_flag():
            return AgentTaskResult(agent_name, None, "Cancelled by user")
        raise
    except RecursionError:
        return AgentTaskResult(
            agent_name,
            None,
            "Recursion depth exceeded. [SYSTEM SUGGESTION]: The sub-agent is looping — "
            "simplify the task or break it into smaller steps.",
        )
    except Exception as e:  # noqa: BLE001
        # No [SYSTEM SUGGESTION]: there is no known fix to suggest.
        return AgentTaskResult(agent_name, None, str(e))
    finally:
        if session is not None and session.active_task is asyncio.current_task():
            session.active_task = None
        if _tracks_activity:
            agent_activity_registry.finish(agent_id, session_id=activity_session_id)
        await fire_subagent_hook(HookEvent.SUBAGENT_STOP, agent_name, agent_id)


def _start_activity_tracking(
    ui: AnyUI,
    agent_id: str,
    agent_name: str,
    task_label: str,
    activity_session_id: str,
) -> bool:
    """Register this run in the activity panel, if the UI has one; return whether it did."""
    if not isinstance(ui, HasActivityTracking):
        return False
    ui.set_activity_id(agent_id)
    ordinal = agent_activity_registry.start(
        agent_id, agent_name, task=task_label, session_id=activity_session_id
    )
    # Label the output stream with the panel ordinal, unless the caller
    # already set a meaningful prefix (background delegation uses its handle).
    if not ui.label:
        ui.set_label(f"[{agent_name} #{ordinal}] ")
    return True


def _register_live_session(
    ui: AnyUI,
    activity_session_id: str,
    agent_id: str,
    agent_name: str,
    sub_agent_manager: SubAgentManagerAPI,
    yolo: bool | None,
    task_text: str,
):
    """Register this run so a human can talk to it while it works.

    Needs the concrete `BufferedUI`. `active_task` lets the TUI's Esc cancel
    exactly this turn; see `LiveSubAgentSessionRegistry.cancel`.
    """
    if not isinstance(ui, BufferedUI):
        return None
    session = get_live_session_registry().add_session(
        activity_session_id,
        agent_id,
        agent_name,
        sub_agent_manager,
        ui,
        yolo_override=yolo,
    )
    session.cancelled_by_human = False  # a fresh run, not a stale flag
    session.active_task = asyncio.current_task()
    start_titling(session, task_text)
    return session


def _finalize_successful_run(
    ui: AnyUI,
    session,
    flush_ui: bool,
    activity_session_id: str,
    agent_id: str,
    agent_name: str,
    history: list,
    result: Any,
) -> Any:
    """Close out a finished delegation and note where its transcript was saved."""
    if flush_ui:
        ui.flush_to_parent()
    get_live_session_registry().mark_turn_finished(
        activity_session_id, agent_id, history
    )
    if session is not None:
        # Cancel/error paths never reach here; they show their own marker.
        session.buffered_ui.append_to_output("<Done>")
    conversation_name = format_delegated_session_name(
        get_current_tool_session(), agent_name, agent_id
    )
    persist_subagent_history(conversation_name, history)
    if session is not None:
        session.persist_history = partial(persist_subagent_history, conversation_name)
    if result:
        return f"{result}\n\n(Transcript saved as '{conversation_name}')"
    return result


def persist_subagent_history(conversation_name: str, history: list) -> None:
    """Save a sub-agent's transcript under its own conversation name (best-effort).

    Each delegation mints a new name, so files are bounded by pruning to
    ``CFG.LLM_SUBAGENT_HISTORY_RETAIN`` after every write; no backup is kept.
    """
    try:
        # lazy: zrb.llm.history_manager transitively loads pydantic_ai.
        from zrb.llm.history_manager.file_history_manager import (
            default_history_manager,
        )

        manager = default_history_manager()
        manager.update(conversation_name, history)
        manager.save(conversation_name, write_backup=False)
        _prune_old_subagent_history()
    except Exception as e:  # noqa: BLE001
        CFG.LOGGER.debug(
            f"Failed to persist sub-agent history '{conversation_name}': {e}"
        )


def _prune_old_subagent_history() -> None:
    """Delete delegated-session history beyond ``CFG.LLM_SUBAGENT_HISTORY_RETAIN``
    (negative keeps all). Best-effort."""
    retain = CFG.LLM_SUBAGENT_HISTORY_RETAIN
    if retain < 0:
        return
    history_dir = os.path.expanduser(CFG.LLM_HISTORY_DIR)
    if not os.path.isdir(history_dir):
        return
    entries = _collect_delegated_history_entries(history_dir)
    if entries is None:
        return
    if len(entries) <= retain:
        return
    entries.sort(key=lambda item: item[0])  # oldest first
    for _mtime, path in entries[: len(entries) - retain]:
        try:
            os.remove(path)
        except OSError:
            pass


def _collect_delegated_history_entries(
    history_dir: str,
) -> list[tuple[float, str]] | None:
    """`(mtime, path)` for every delegated transcript, or None if a directory
    cannot be scanned."""
    # Only `subagent/{agent_type}/`, never the root: a user session whose name
    # merely looks delegated must never be deleted.
    entries: list[tuple[float, str]] = []
    try:
        for directory in subagent_only_directories(history_dir):
            with os.scandir(directory) as it:
                for entry in it:
                    if not entry.name.endswith(".json"):
                        continue
                    if parse_delegated_session(entry.name[: -len(".json")]) is None:
                        continue
                    try:
                        entries.append((entry.stat().st_mtime, entry.path))
                    except OSError:
                        continue
    except OSError:
        return None
    return entries


async def fire_subagent_hook(event: HookEvent, agent_name: str, agent_id: str) -> None:
    """Fire SubagentStart/Stop (observe-only) on the parent run's hook manager,
    falling back to the module singleton. Never raises."""
    manager = get_run_hook_manager()
    try:
        await manager.execute_hooks(
            event,
            {"agent_type": agent_name, "agent_id": agent_id},
            agent_type=agent_name,
            agent_id=agent_id,
        )
    except asyncio.CancelledError:
        # Swallowed: this also fires from a `finally`, where a stray cancel
        # must not override an already-settled result.
        CFG.LOGGER.debug(f"Delegation hook '{event}' cancelled")
    except Exception as e:
        CFG.LOGGER.debug(f"Delegation hook '{event}' failed: {e}")


def _delegatable_agents(sub_agent_manager: SubAgentManagerAPI) -> list:
    """Agents the current permission policy permits delegating to."""
    # lazy: tests patch zrb.llm.permission.get_effective_policy; hoisting bypasses the mock
    from zrb.llm.permission import DENY, get_effective_policy

    agents = sub_agent_manager.scan()
    policy = get_effective_policy()
    if policy is None:
        return agents
    return [
        a
        for a in agents
        if policy.decide("DelegateToAgent", Capability.DELEGATE, {"agent_name": a.name})
        != DENY
    ]


def _sort_agents(agents: list) -> list:
    """Put built-in core agents first, then sort each group by name."""
    return sorted(
        agents,
        key=lambda agent: (
            0 if "core_agents" in Path(agent.path).parts else 1,
            agent.name,
        ),
    )


def agent_roster_doc(sub_agent_manager: SubAgentManagerAPI) -> str:
    """The `AVAILABLE AGENTS` block for a delegation tool's docstring.

    Capped by ``LLM_MAX_AGENTS_IN_ROSTER``; the overflow points to ``SearchAgent``.
    """
    agents = _delegatable_agents(sub_agent_manager)
    if not agents:
        return "- No sub-agents found."
    agents = _sort_agents(agents)
    shown, hidden = cap_items(agents, CFG.LLM_MAX_AGENTS_IN_ROSTER)
    lines = "\n".join(f"- `{a.name}`: {a.description}" for a in shown)
    if hidden > 0:
        lines += f"\n(+{hidden} more — use SearchAgent to find them)"
    return lines


def agent_not_found_message(
    agent_name: str, sub_agent_manager: SubAgentManagerAPI
) -> str:
    """Error text for an unknown `agent_name`, with the closest match and the valid names."""
    names = [a.name for a in _sort_agents(_delegatable_agents(sub_agent_manager))]
    if not names:
        return (
            f"Sub-agent '{agent_name}' not found: no sub-agents are registered. "
            "[SYSTEM SUGGESTION]: Do the work yourself — delegation is "
            "unavailable in this session."
        )
    close = suggest_name(agent_name, names, limit=1)
    suggestion = f" Did you mean '{close[0]}'?" if close else ""
    shown, hidden = cap_items(names, CFG.LLM_MAX_AGENTS_IN_ROSTER)
    more = f", and {hidden} more (use SearchAgent to list them)" if hidden > 0 else ""
    return (
        f"Sub-agent '{agent_name}' not found.{suggestion} "
        f"[SYSTEM SUGGESTION]: Available agents are: {', '.join(shown)}{more}. "
        "Call again with one of these exact names, or do the work yourself."
    )


async def _git_output(cwd: str, *args: str) -> tuple[int, str]:
    """Run ``git *args`` in *cwd*; return (returncode, stripped stdout)."""
    proc = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    return proc.returncode or 0, stdout.decode().strip()


async def worktree_has_changes(worktree_path: str) -> bool:
    """Whether *worktree_path* has any uncommitted change (`git status --short`)."""
    _, out = await _git_output(worktree_path, "status", "--short")
    return bool(out)


async def current_head_sha(cwd: str) -> str:
    """``git rev-parse HEAD`` in *cwd*, or ``""`` if it fails."""
    code, out = await _git_output(cwd, "rev-parse", "HEAD")
    return out if code == 0 else ""


async def worktree_has_new_commits(worktree_path: str, base_sha: str) -> bool:
    """Whether *worktree_path*'s branch has any commit beyond *base_sha*.

    A sub-agent that commits its work leaves a clean tree; this keeps cleanup
    from force-deleting those commits. Unknown answers return True (fail safe).
    """
    if not base_sha:
        return True
    code, count = await _git_output(
        worktree_path, "rev-list", "--count", f"{base_sha}..HEAD"
    )
    if code != 0:
        return True
    return count.isdigit() and int(count) > 0


def _cut_waiter() -> "asyncio.Task | None":
    """A task that finishes when this turn is needed back, or None outside a run.

    The generation is read before waiting, so a keypress that arrived during an
    earlier tool call does not move work that had not started yet.
    """
    cut = get_run_shell_cut_signal()
    if cut is None:
        return None
    return asyncio.ensure_future(cut.wait_for_cut(cut.generation))


async def _stop_waiter(waiter: "asyncio.Task | None") -> None:
    """Cancel a waiter nobody needs any more, and never let its outcome escape."""
    if waiter is None or waiter.done():
        return
    waiter.cancel()
    await asyncio.gather(waiter, return_exceptions=True)


async def _stop_runs(runs: "list[asyncio.Task]") -> None:
    """Stop delegations whose turn is being cancelled.

    The turn that would have reported them is gone, so they stop with it — the
    behaviour they had before a cut could move them anywhere.
    """
    for run in runs:
        run.cancel()
    await asyncio.gather(*runs, return_exceptions=True)


async def _has_run_finished(run: asyncio.Task, cut_wait: "asyncio.Task | None") -> bool:
    """Whether *run* finished, rather than a cut asking this turn to move on."""
    if cut_wait is None:
        await asyncio.wait({run})
        return True
    done, _ = await asyncio.wait({run, cut_wait}, return_when=asyncio.FIRST_COMPLETED)
    return run in done


async def _wait_for_runs(
    runs: "list[asyncio.Task]", cut_wait: "asyncio.Task | None"
) -> None:
    """Wait for every run, or for the cut that asks this turn to move on.

    Runs still going when it returns are left running: a cut hands them to the
    background registry, and it never cancels one.
    """
    pending = set(runs)
    while pending:
        waiters = pending if cut_wait is None else pending | {cut_wait}
        done, _ = await asyncio.wait(waiters, return_when=asyncio.FIRST_COMPLETED)
        if cut_wait is not None and cut_wait in done:
            return
        pending -= done


def _adopt_delegation(
    run: asyncio.Task, buffered_ui: BufferedUI, agent_name: str
) -> str:
    """Hand a still-running delegation to the background registry; return its handle.

    The task keeps running: only its result changes hands, from this tool call
    to `GetDelegationResult`. Its buffered transcript goes with it, so what the
    sub-agent has already printed stays readable there.
    """
    # lazy: circular — delegate_background imports this module's BufferedUI and
    # run_agent_task, so this direction has to stay deferred.
    from zrb.llm.tool.delegate_background import (
        get_background_registry,
        register_background_handle,
    )

    handle = get_random_name(separator="-", add_random_digit=True)
    get_background_registry().adopt(
        handle, agent_name, run, buffered_ui, buffered_ui.session_id
    )
    register_background_handle(handle)
    return handle


def _moved_to_background_note(handle: str, agent_name: str) -> str:
    """Report a delegation that is still running, and how to reach it."""
    call = f"GetDelegationResult(handle='{handle}'"
    return (
        f"Handle: {handle}\n"
        "[SYSTEM SUGGESTION]: The user sent a message that needs this turn while "
        f"the sub-agent '{agent_name}' was running, so the delegation was moved "
        f"to the background as '{handle}' instead of holding the turn. Read the "
        "message first. It was NOT cancelled, and the work it has already done "
        f"is not lost. Call {call}) to read what it has produced so far, {call}, "
        f"wait=30) to block for it, or {call}, kill=True) to stop it. Do not "
        "delegate the same work again: that starts a second copy."
    )


def _moved_siblings_note(moved: "list[tuple[str, str]]", total: int) -> str:
    """Report fanned-out sub-agents that are still running, one handle each.

    *moved* is ``(handle, agent_name)`` in fan-out order; *total* is how many
    the call asked for, so the model can tell how much came back now.
    """
    listing = ", ".join(f"'{handle}' ({agent_name})" for handle, agent_name in moved)
    calls = ", ".join(f"GetDelegationResult(handle='{handle}')" for handle, _ in moved)
    return (
        f"Handles: {listing}\n"
        "[SYSTEM SUGGESTION]: The user sent a message that needs this turn while "
        f"{len(moved)} of the {total} sub-agents in this fan-out were still "
        "running, so those were moved to the background instead of holding the "
        "turn. Read the message first. None was cancelled, and the work they "
        f"have already done is not lost. Call {calls} to collect each result as "
        "it finishes (wait=N blocks for one, kill=True stops it). Do not "
        "delegate the same work again: that starts a second copy."
    )


async def _run_delegation(
    agent_name: str,
    deliverable: str,
    non_goals: list[str],
    task: str,
    additional_context: str,
    sub_agent_manager: SubAgentManagerAPI,
    buffered_ui: BufferedUI,
) -> str:
    """Run one sub-agent for this turn, or step it aside when the user needs the turn.

    The sub-agent is a `Task` from the start, so a cut hands exactly that task to
    the background registry: an awaited task nobody waits on any more keeps
    running, which is what keeps the work alive when the turn is interrupted
    instead of waiting.
    """
    run = asyncio.ensure_future(
        run_agent_task(
            agent_name=agent_name,
            deliverable=deliverable,
            non_goals=non_goals,
            task=task,
            additional_context=additional_context,
            sub_agent_manager=sub_agent_manager,
            ui=buffered_ui,
        )
    )
    cut_wait = _cut_waiter()
    try:
        finished = await _has_run_finished(run, cut_wait)
    except asyncio.CancelledError:
        await _stop_runs([run])
        raise
    finally:
        await _stop_waiter(cut_wait)

    if not finished:
        return _moved_to_background_note(
            _adopt_delegation(run, buffered_ui, agent_name), agent_name
        )
    task_result: AgentTaskResult = run.result()
    if not task_result.success:
        return f"Error: {task_result.error}"
    label = buffered_ui.label or f"[{agent_name}]"
    return f"{label} completed:\n\n{task_result.result}"


async def _run_parallel(
    tasks: list[dict[str, Any]],
    sub_agent_manager: SubAgentManagerAPI,
) -> str:
    """Run several sub-agent tasks concurrently and return combined results.

    A shared lock serializes approval prompts. ``isolate_worktree: true`` gives
    a task its own git worktree; each `Task` copies `contextvars`, so
    `active_worktree` stays isolated per task.
    """
    required = ("agent_name", "deliverable", "task", "non_goals")
    for idx, spec in enumerate(tasks):
        missing = [k for k in required if k not in spec]
        if missing:
            return (
                f"Error: tasks[{idx}] missing required keys: {missing}. "
                "[SYSTEM SUGGESTION]: every task needs agent_name, "
                "deliverable, task, and non_goals (list; [] allowed)."
            )

    parent_ui = resolve_ui(get_current_ui())
    ui_lock = asyncio.Lock()
    # Caps concurrent runs; 0/negative disables the cap.
    _max_parallel = CFG.LLM_MAX_PARALLEL_DELEGATIONS
    _fan_out_semaphore = asyncio.Semaphore(_max_parallel) if _max_parallel > 0 else None

    async def _run_single_agent_inner(
        task_spec: dict[str, Any], buffered_ui: BufferedUI
    ) -> AgentTaskResult:
        agent_name = task_spec.get("agent_name", "")
        deliverable = task_spec.get("deliverable", "")
        task = task_spec.get("task", "")
        non_goals = task_spec.get("non_goals", []) or []
        additional_context = task_spec.get("additional_context", "")
        isolate = bool(task_spec.get("isolate_worktree", False))

        worktree_path = ""
        base_sha = ""
        if isolate:
            base_sha = await current_head_sha(os.getcwd())
            # enter_worktree's default name is second-granular; concurrent
            # tasks would collide.
            branch_name = f"delegate-{agent_name}-{get_random_name(separator='-', add_random_digit=True)}"
            enter_msg = await enter_worktree(branch_name=branch_name)
            worktree_path = get_active_worktree()
            if not worktree_path:
                return AgentTaskResult(
                    buffered_ui.label or f"[{agent_name}]", None, enter_msg
                )

        result: AgentTaskResult | None = None
        try:
            result = await run_agent_task(
                agent_name=agent_name,
                deliverable=deliverable,
                non_goals=non_goals,
                task=task,
                additional_context=additional_context,
                sub_agent_manager=sub_agent_manager,
                ui=buffered_ui,
                flush_ui=False,
                yolo=None,
            )
        finally:
            # A cleanup failure must not escape and abort the sibling tasks.
            if isolate and worktree_path:
                try:
                    dirty = await worktree_has_changes(worktree_path)
                    has_new_commits = await worktree_has_new_commits(
                        worktree_path, base_sha
                    )
                    if dirty or has_new_commits:
                        if result is not None and result.success and result.result:
                            result.result += f"\n\n(Worktree left in place for review: {worktree_path})"
                    else:
                        await exit_worktree(worktree_path)
                except Exception as e:  # noqa: BLE001
                    CFG.LOGGER.debug(
                        f"Worktree cleanup failed for {worktree_path}: {e}"
                    )
                    if result is not None and result.success and result.result:
                        result.result += (
                            "\n\n(Worktree cleanup failed — left in place for "
                            f"manual review: {worktree_path}: {e})"
                        )

        assert result is not None
        return AgentTaskResult(
            buffered_ui.label or f"[{agent_name}]",
            result.result,
            result.error,
        )

    async def run_single_agent(
        task_spec: dict[str, Any], buffered_ui: BufferedUI
    ) -> AgentTaskResult:
        if _fan_out_semaphore is None:
            return await _run_single_agent_inner(task_spec, buffered_ui)
        async with _fan_out_semaphore:
            return await _run_single_agent_inner(task_spec, buffered_ui)

    # One buffer and one `Task` per delegation, rather than one `gather`: a cut
    # hands the still-running ones to the background registry, and a frame
    # cancelled with its turn takes no child task down with it.
    buffered_uis = [_fan_out_buffer(parent_ui, ui_lock) for _ in tasks]
    runs = [
        asyncio.ensure_future(run_single_agent(spec, buffered_ui))
        for spec, buffered_ui in zip(tasks, buffered_uis)
    ]
    cut_wait = _cut_waiter()
    try:
        await _wait_for_runs(runs, cut_wait)
    except asyncio.CancelledError:
        await _stop_runs(runs)
        raise
    finally:
        await _stop_waiter(cut_wait)

    agent_names = [spec.get("agent_name", "") for spec in tasks]
    return "\n\n".join(_fan_out_reports(agent_names, buffered_uis, runs))


def _fan_out_buffer(parent_ui: "AnyUI", ui_lock: asyncio.Lock) -> BufferedUI:
    """One fanned-out delegation's output buffer; `run_agent_task` labels it.

    Built here rather than inside the task so the buffer is known to this frame:
    a cut adopts a task together with the buffer holding its transcript.
    """
    return BufferedUI(
        parent_ui,
        shared_lock=ui_lock,
        session_id=get_session_ownership_key(get_current_tool_session()),
    )


def _fan_out_reports(
    agent_names: list[str], buffered_uis: list[BufferedUI], runs: "list[asyncio.Task]"
) -> list[str]:
    """One report per finished delegation, then one handle list for the rest.

    A delegation still running when the turn was needed back is adopted, not
    cancelled: its handle is reported so its result can be collected later.
    """
    reports = [
        _fan_out_report(agent_name, run)
        for agent_name, run in zip(agent_names, runs)
        if run.done()
    ]
    moved = [
        (_adopt_delegation(run, buffered_ui, agent_name), agent_name)
        for agent_name, buffered_ui, run in zip(agent_names, buffered_uis, runs)
        if not run.done()
    ]
    if moved:
        reports.append(_moved_siblings_note(moved, len(runs)))
    return reports


def _fan_out_report(agent_name: str, run: asyncio.Task) -> str:
    """One finished delegation's report; its own failure stays its own line.

    An unanticipated raise fails one task, not every sibling — the guarantee
    `gather(return_exceptions=True)` used to give this loop.
    """
    if run.cancelled():
        return f"[{agent_name}] Error: cancelled"
    error = run.exception()
    if error is not None:
        return f"[{agent_name}] Error: {error}"
    result: AgentTaskResult = run.result()
    # result.agent_name already carries its [agent_name #ordinal] label.
    if not result.success:
        return f"{result.agent_name} Error: {result.error}"
    indented_result = "\n".join(
        ["  " + line for line in (result.result or "").splitlines()]
    )
    return f"{result.agent_name} completed:\n{indented_result}"


def create_delegate_to_agent_tool(
    sub_agent_manager: SubAgentManagerAPI | None = None,
):
    if sub_agent_manager is None:
        sub_agent_manager = default_sub_agent_manager()
    agent_doc_section = agent_roster_doc(sub_agent_manager)

    async def delegate_to_agent(
        agent_name: Annotated[
            str,
            Field(
                description=(
                    "Name of the sub-agent to delegate to (see AVAILABLE AGENTS "
                    "in this tool's description)."
                )
            ),
        ] = "",
        deliverable: Annotated[
            str,
            Field(
                description=(
                    "Concrete artifact that must exist on return — name the "
                    "file, function, or decision."
                )
            ),
        ] = "",
        task: Annotated[
            str,
            Field(
                description=(
                    "How to produce the deliverable — reference exact files, "
                    "line numbers, or commands when known."
                )
            ),
        ] = "",
        # `= []` is safe (pydantic copies mutable defaults) and keeps the
        # schema free of an anyOf-null union.
        non_goals: Annotated[
            list[str],
            Field(
                description=(
                    "Things the sub-agent must NOT do (scope clamp). Pass [] "
                    "only when certain."
                )
            ),
        ] = [],  # noqa: B006
        additional_context: Annotated[
            str,
            Field(
                description=(
                    "Extra background the sub-agent needs that doesn't belong "
                    "in deliverable/task/non_goals."
                )
            ),
        ] = "",
        tasks: Annotated[
            list[dict[str, Any]],
            Field(
                description=(
                    "Fan out: a list of task dicts (agent_name, deliverable, "
                    "task, non_goals, ...) to run concurrently in one call. "
                    "When non-empty, the flat args above are ignored."
                )
            ),
        ] = [],  # noqa: B006
    ) -> str:
        """See module docstring; required-arg signature is the scope clamp."""
        if tasks:
            return await _run_parallel(tasks, sub_agent_manager)
        missing = [
            name
            for name, value in (
                ("agent_name", agent_name),
                ("deliverable", deliverable),
                ("task", task),
            )
            if not value
        ]
        if missing:
            return (
                f"Error: missing required args: {missing}. "
                "[SYSTEM SUGGESTION]: provide agent_name, deliverable, and task "
                "(non_goals defaults to []), or pass tasks=[...] to fan out."
            )
        parent_ui = resolve_ui(get_current_ui())
        # run_agent_task assigns the [agent_name #ordinal] label. Built here so a
        # cut can adopt the transcript along with the run.
        buffered_ui = BufferedUI(
            parent_ui,
            session_id=get_session_ownership_key(get_current_tool_session()),
        )

        return await _run_delegation(
            agent_name=agent_name,
            deliverable=deliverable,
            non_goals=non_goals,
            task=task,
            additional_context=additional_context,
            sub_agent_manager=sub_agent_manager,
            buffered_ui=buffered_ui,
        )

    setattr(delegate_to_agent, "zrb_is_delegate_tool", True)
    delegate_to_agent.__name__ = "DelegateToAgent"
    delegate_to_agent.__doc__ = (
        "Delegates a task to a named subagent for isolated execution.\n\n"
        "The envelope is the contract — a vague envelope comes back vague; "
        "see each parameter's own description.\n\n"
        "For a comparative deliverable, set the axes yourself and give every "
        "sub-agent the same list — reports built on different frames cannot be "
        "reconciled.\n\n"
        "FAN OUT: pass tasks=[{agent_name, deliverable, task, non_goals, ...}, ...] to run multiple "
        "sub-agents concurrently in one call. Flat args are ignored when tasks is non-empty.\n\n"
        "ISOLATE_WORKTREE: add isolate_worktree: true to a task in the fan-out list to give "
        "that task its own git worktree instead of the shared working tree. Use it when two or "
        "more fanned-out tasks will WRITE to overlapping files — concurrent writes on one tree "
        "corrupt each other. The worktree is removed automatically if the task leaves it clean; "
        "if it has changes, the worktree is left in place and its path is reported so you (and the "
        "user) can review and merge it manually.\n\n"
        f"AVAILABLE AGENTS:\n{agent_doc_section}"
    )
    tag(delegate_to_agent, Capability.DELEGATE)
    return delegate_to_agent


def create_search_agent_tool(
    sub_agent_manager: SubAgentManagerAPI | None = None,
):
    if sub_agent_manager is None:
        sub_agent_manager = default_sub_agent_manager()

    async def search_agent(
        query: Annotated[
            str,
            Field(
                description=(
                    "Free-text match against agent name/description. Empty "
                    "returns every agent."
                )
            ),
        ] = "",
    ) -> str:
        agents = _sort_agents(_delegatable_agents(sub_agent_manager))
        return search_roster(agents, query) or _no_agent_match_message(query)

    setattr(search_agent, "zrb_is_delegate_tool", True)
    search_agent.__name__ = "SearchAgent"
    # No roster here: this tool is the window onto what the delegation
    # tools' rosters truncate.
    search_agent.__doc__ = (
        "Searches the sub-agent roster by name or description.\n\n"
        "Use it when the AVAILABLE AGENTS roster in a delegation tool is "
        "truncated, or you need an agent not listed there.\n\n"
        "query: words to match against agent names and descriptions "
        "(case-insensitive). Leave empty to list delegatable agents unfiltered; "
        "the listing caps at 30 matches — narrow the query for the rest."
    )
    tag(search_agent, Capability.DELEGATE)
    return search_agent


def _no_agent_match_message(query: str) -> str:
    """Text for an empty search result, naming the way back."""
    if query.strip():
        return (
            f"No agents match '{query.strip()}'. [SYSTEM SUGGESTION]: retry with "
            "broader terms — matching covers agent names and descriptions."
        )
    return "No delegatable agents are registered."
