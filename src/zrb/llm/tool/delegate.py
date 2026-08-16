from __future__ import annotations

import asyncio
import difflib
import os
import uuid
from dataclasses import dataclass
from typing import Any

from zrb.config.config import CFG
from zrb.llm.agent.activity import HasActivityTracking, agent_activity_registry
from zrb.llm.agent.run.runner import run_agent
from zrb.llm.agent.run.runtime_state import get_current_hook_manager, get_current_ui
from zrb.llm.agent.subagent.live_session import live_subagent_session_registry

# Import directly from the inner module to avoid a circular import: the
# subagent package's __init__ triggers `apply_common_tools`, which loads
# zrb.llm.tool, which loads this module — so the package __init__ is still
# mid-load when delegate.py executes its imports.
from zrb.llm.agent.subagent.manager import (
    SubAgentManager,
)
from zrb.llm.agent.subagent.manager import (
    sub_agent_manager as default_sub_agent_manager,
)
from zrb.llm.config.limiter import llm_limiter
from zrb.llm.hook.manager import hook_manager as default_hook_manager
from zrb.llm.hook.types import HookEvent
from zrb.llm.permission import Capability, tag
from zrb.llm.tool.ambient_state import get_active_worktree, get_current_tool_session
from zrb.llm.tool.worktree import enter_worktree, exit_worktree
from zrb.llm.tool_call.ui_protocol import UIProtocol
from zrb.llm.ui.buffered_ui import BufferedUI
from zrb.llm.ui.std_ui import StdUI
from zrb.llm.util.subagent_session_naming import (
    format_delegated_session_name,
    parse_delegated_session,
    subagent_only_directories,
)
from zrb.util.string.name import get_random_name

# On-demand search results are themselves capped so an unscoped query (or an
# empty one) cannot dump the whole roster in one answer. 30 entries keeps a
# full page of matches visible while still bounding a runaway listing.
_SEARCH_RESULT_LIMIT = 30


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
    """Assemble a scope-clamped envelope the sub-agent reads first.

    The DELIVERABLE / NON-GOALS / TASK / CONTEXT / BEFORE RETURNING delimiters
    are intentionally uppercase and structural so a sub-agent cannot miss the
    fence while parsing free-form prose.
    """
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


async def _run_agent_task(
    agent_name: str,
    deliverable: str,
    non_goals: list[str],
    task: str,
    additional_context: str,
    sub_agent_manager: SubAgentManager,
    ui: UIProtocol,
    flush_ui: bool = False,
    yolo: bool | None = None,
) -> AgentTaskResult:
    """Run a single agent task and return structured result.

    Args:
        yolo: Override yolo for the sub-agent. None = inherit from parent.
    """
    sub_agent = sub_agent_manager.create_agent(agent_name, yolo=yolo)
    if not sub_agent:
        return AgentTaskResult(
            agent_name,
            None,
            agent_not_found_message(agent_name, sub_agent_manager),
        )

    full_message = _format_envelope(deliverable, non_goals, task, additional_context)

    # SubagentStart/Stop fire on the parent run's hook manager (Claude semantics:
    # the parent observes its subagents). agent_type is the delegated agent's name.
    agent_id = uuid.uuid4().hex[:8]
    # Scopes the activity-panel entry to this run's own session, so a process
    # hosting multiple sessions (the web runner) doesn't bleed one session's
    # running sub-agents into another's panel/listing.
    activity_session_id = get_current_tool_session()
    _tracks_activity = isinstance(ui, HasActivityTracking)
    if _tracks_activity:
        ui.set_activity_id(agent_id)
        ordinal = agent_activity_registry.start(
            agent_id,
            agent_name,
            task=deliverable or task,
            session_id=activity_session_id,
        )
        # Label the output stream with the panel ordinal, unless the caller
        # already set a meaningful prefix (background delegation uses its handle).
        if not ui.label:
            ui.set_label(f"[{agent_name} #{ordinal}] ")
    # The "talk to a running sub-agent directly" feature (live_session.py)
    # needs the concrete BufferedUI (its buffer + active_run_context), not
    # just the HasActivityTracking protocol — registered unconditionally
    # here since it's the one place all three delegate paths (single,
    # fan-out, background) construct their BufferedUI and share this code.
    # active_task lets the TUI's Esc (while viewing this sub-agent) cancel
    # exactly this turn; see `LiveSubAgentSessionRegistry.cancel`.
    session = None
    if isinstance(ui, BufferedUI):
        session = live_subagent_session_registry.add_session(
            activity_session_id, agent_id, agent_name, sub_agent_manager, ui
        )
        session.cancelled_by_human = False  # a fresh run, not a stale flag
        session.active_task = asyncio.current_task()
    try:
        # Fired inside the try (not before it): a cancel landing exactly
        # during this await must go through the same handling as every other
        # cancellation below (check `consume_cancelled_flag`), not propagate
        # uncaught — in the single-delegate path `session.active_task` is the
        # same asyncio Task driving the whole main turn, so an uncaught
        # propagation here would kill the entire turn, not just this call.
        await _fire_subagent_hook(HookEvent.SUBAGENT_START, agent_name, agent_id)
        result, history = await run_agent(
            agent=sub_agent,
            message=full_message,
            message_history=[],
            limiter=llm_limiter,
            ui=ui,
            yolo=bool(yolo) if yolo is not None else yolo,
        )

        if flush_ui and hasattr(ui, "flush_to_parent"):
            getattr(ui, "flush_to_parent")()

        live_subagent_session_registry.mark_turn_finished(
            activity_session_id, agent_id, history
        )
        if session is not None:
            # End-of-session marker for the sub-agent's live view, appended
            # after the turn went idle so the transcript visibly ends. Cancel
            # and error paths never reach here — those show "<Esc> Canceled"
            # (written by the TUI's cancel_viewed_agent) or the error instead.
            session.buffered_ui.append_to_output("<Done>")

        # Every completed delegation persists its transcript under a derived
        # conversation name, bounded by LLM_SUBAGENT_HISTORY_RETAIN. No knob
        # gates it: unlike ordinary sessions (re-saved under one name) each
        # delegation is written exactly once, so the bounded pruning is the
        # only thing that keeps it from filling the disk.
        conversation_name = format_delegated_session_name(
            get_current_tool_session(), agent_name, agent_id
        )
        _persist_subagent_history(conversation_name, history)
        if result:
            result = f"{result}\n\n(Transcript saved as '{conversation_name}')"

        return AgentTaskResult(agent_name, result, None)

    except asyncio.CancelledError:
        # The human pressed Esc while viewing this sub-agent (TUI) and
        # `cancel()` flagged it. Kill only this sub-agent's turn: return a
        # cancelled result so the main agent (which may be awaiting this
        # delegation — e.g. in a fan-out's `asyncio.gather`) continues with a
        # normal result instead of being cancelled too. A cancellation not
        # initiated by `cancel()` (the main run's own Esc) re-raises.
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
        # No [SYSTEM SUGGESTION] here, unlike RecursionError above: that's a
        # specific, recognizable failure mode with a known fix (simplify the
        # task); an arbitrary sub-agent exception isn't — guessing generic
        # recovery advice for an unknown cause would be more likely to
        # mislead the parent agent than to help it.
        return AgentTaskResult(agent_name, None, str(e))
    finally:
        if session is not None and session.active_task is asyncio.current_task():
            session.active_task = None
        if _tracks_activity:
            agent_activity_registry.finish(agent_id, session_id=activity_session_id)
        await _fire_subagent_hook(HookEvent.SUBAGENT_STOP, agent_name, agent_id)


def _persist_subagent_history(conversation_name: str, history: list) -> None:
    """Save a delegated sub-agent's transcript under its own conversation name
    (ADR item 4, Phase A), always — there is no opt-out knob.

    Best-effort: persisting the transcript is not this tool's primary job, so
    a failure here (disk full, permissions) must not surface as a delegation
    failure — same posture as ``_fire_subagent_hook``.

    Unlike an ordinary conversation (one name, re-saved across turns, where
    ``LLM_HISTORY_BACKUP_RETAIN`` bounds its backups), every delegation mints
    a brand-new, never-reused ``conversation_name`` — so nothing bounds these
    files on its own. Two things keep that from filling the disk on a
    long-running or heavily-delegating session: no backup is written for a
    session that's never resaved (``write_backup=False``), and
    ``_prune_old_subagent_history`` deletes the oldest ones past
    ``CFG.LLM_SUBAGENT_HISTORY_RETAIN`` right after every write.
    """
    try:
        # lazy: zrb.llm.history_manager transitively loads pydantic_ai.
        from zrb.llm.history_manager.file_history_manager import FileHistoryManager

        manager = FileHistoryManager(history_dir=CFG.LLM_HISTORY_DIR)
        manager.update(conversation_name, history)
        manager.save(conversation_name, write_backup=False)
        _prune_old_subagent_history()
    except Exception as e:  # noqa: BLE001
        CFG.LOGGER.debug(
            f"Failed to persist sub-agent history '{conversation_name}': {e}"
        )


def _prune_old_subagent_history() -> None:
    """Delete the oldest delegated-session history files beyond
    ``CFG.LLM_SUBAGENT_HISTORY_RETAIN``, keeping always-on persistence safe.
    ``-1`` opts out (keep every one, at the caller's own risk); errors are
    swallowed (best-effort, see ``_persist_subagent_history``)."""
    retain = CFG.LLM_SUBAGENT_HISTORY_RETAIN
    if retain < 0:
        return
    history_dir = os.path.expanduser(CFG.LLM_HISTORY_DIR)
    if not os.path.isdir(history_dir):
        return
    # Scoped to `subagent/{agent_type}/` only — never the flat history root.
    # The root also holds ordinary (non-delegated) sessions, and a session
    # name that merely *looks* delegated (matches `parse_delegated_session`'s
    # best-effort shape, e.g. a user `/save`d name) must never become a
    # deletion candidate. Cost: legacy delegated files written before the
    # `subagent/` layout shipped (which live flat in the root) are no longer
    # pruned by this pass — they simply accumulate, same as before this
    # feature existed. Reads/search still scan both locations (see
    # `subagent_history_directories`); only pruning is narrowed.
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
        return
    if len(entries) <= retain:
        return
    entries.sort(key=lambda item: item[0])  # oldest first
    for _mtime, path in entries[: len(entries) - retain]:
        try:
            os.remove(path)
        except OSError:
            pass


async def _fire_subagent_hook(event: HookEvent, agent_name: str, agent_id: str) -> None:
    """Fire SubagentStart/Stop (observe-only) on the parent run's hook manager,
    falling back to the module singleton. Never raises."""
    manager = get_current_hook_manager() or default_hook_manager
    try:
        await manager.execute_hooks(
            event,
            {"agent_type": agent_name, "agent_id": agent_id},
            agent_type=agent_name,
            agent_id=agent_id,
        )
    except asyncio.CancelledError:
        # `asyncio.CancelledError` is a `BaseException`, not caught by the
        # `Exception` branch below — swallowed deliberately so "Never raises"
        # is actually true. This call fires from `_run_agent_task`'s `finally`
        # block too, after its result is already decided; a stray cancel
        # landing in this narrow best-effort notification must not override
        # an already-settled return. It is not the cancellation signal the
        # sub-agent's own turn responds to (that's handled separately, via
        # `session.consume_cancelled_flag`), so absorbing it here costs nothing.
        CFG.LOGGER.debug(f"Delegation hook '{event}' cancelled")
    except Exception as e:
        CFG.LOGGER.debug(f"Delegation hook '{event}' failed: {e}")


def _delegatable_agents(sub_agent_manager: SubAgentManager) -> list:
    """Agents the current permission policy permits delegating to.

    With no policy in force (the default), every scanned agent is returned.
    When a policy denies delegation to a specific agent, it is omitted from the
    advertised roster so the model isn't offered an option it cannot use.
    """
    # lazy: tests patch zrb.llm.permission.get_effective_policy; hoisting
    # would bind the name at this module's load time and bypass the mock.
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


def agent_roster_doc(sub_agent_manager: SubAgentManager) -> str:
    """The `AVAILABLE AGENTS` block for a delegation tool's docstring.

    Every tool that takes an `agent_name` embeds this, so the valid names are
    in each tool's own schema rather than recalled from a sibling's. The roster
    is capped by ``LLM_MAX_AGENTS_IN_ROSTER`` with a pointer to ``SearchAgent``:
    a huge sub-agent fleet must not inflate every request's docstrings, and the
    overflow stays reachable on demand.
    """
    agents = _delegatable_agents(sub_agent_manager)
    if not agents:
        return "- No sub-agents found."
    # Sort by name so the roster (and its truncation boundary) is deterministic:
    # the scan is filesystem-ordered, and once the cap cuts the list the visible
    # subset must not depend on readdir order.
    agents = sorted(agents, key=lambda a: a.name)
    cap = CFG.LLM_MAX_AGENTS_IN_ROSTER
    shown = agents if cap < 1 else agents[:cap]
    lines = "\n".join(f"- `{a.name}`: {a.description}" for a in shown)
    hidden = len(agents) - len(shown)
    if hidden > 0:
        lines += f"\n(+{hidden} more — use SearchAgent to find them)"
    return lines


def agent_not_found_message(agent_name: str, sub_agent_manager: SubAgentManager) -> str:
    """Error text for an unknown `agent_name`, naming the valid ones.

    The previous text said only "Check DelegateToAgent's description for
    available sub-agents" — an instruction to re-read something the model
    already has and just misread, which makes the next attempt another guess.
    The names are cheap; spelling them out here turns the retry into a
    correction. The closest match is offered first because the usual failure is
    a near-miss (`research` for `researcher`, or a name carried over from a
    different harness's roster).
    """
    names = sorted(a.name for a in _delegatable_agents(sub_agent_manager))
    if not names:
        return (
            f"Sub-agent '{agent_name}' not found: no sub-agents are registered. "
            "[SYSTEM SUGGESTION]: Do the work yourself — delegation is "
            "unavailable in this session."
        )
    close = difflib.get_close_matches(agent_name, names, n=1, cutoff=0.6)
    suggestion = f" Did you mean '{close[0]}'?" if close else ""
    cap = CFG.LLM_MAX_AGENTS_IN_ROSTER
    shown = names if cap < 1 else names[:cap]
    hidden = len(names) - len(shown)
    more = f", and {hidden} more (use SearchAgent to list them)" if hidden > 0 else ""
    return (
        f"Sub-agent '{agent_name}' not found.{suggestion} "
        f"[SYSTEM SUGGESTION]: Available agents are: {', '.join(shown)}{more}. "
        "Call again with one of these exact names, or do the work yourself."
    )


async def _worktree_has_changes(worktree_path: str) -> bool:
    """Whether *worktree_path* has any uncommitted change (`git status --short`)."""
    proc = await asyncio.create_subprocess_exec(
        "git",
        "status",
        "--short",
        cwd=worktree_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    return bool(stdout.decode().strip())


async def _current_head_sha(cwd: str) -> str:
    """``git rev-parse HEAD`` in *cwd*, or ``""`` if it fails."""
    proc = await asyncio.create_subprocess_exec(
        "git",
        "rev-parse",
        "HEAD",
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    if proc.returncode != 0:
        return ""
    return stdout.decode().strip()


async def _worktree_has_new_commits(worktree_path: str, base_sha: str) -> bool:
    """Whether *worktree_path*'s branch has any commit beyond *base_sha*.

    ``_worktree_has_changes`` alone only sees uncommitted changes — a
    sub-agent that *commits* its deliverable makes the tree clean, which
    would otherwise let cleanup force-delete the branch (and its commits)
    via `exit_worktree`'s default `keep_branch=False`. This closes that gap:
    a non-empty ``base_sha..HEAD`` range means real work exists on the
    branch, regardless of working-tree cleanliness.
    """
    if not base_sha:
        # Couldn't determine the fork point (e.g. `rev-parse` failed before
        # entering the worktree) — fail safe and assume there might be
        # commits rather than risk deleting real work.
        return True
    proc = await asyncio.create_subprocess_exec(
        "git",
        "rev-list",
        "--count",
        f"{base_sha}..HEAD",
        cwd=worktree_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    if proc.returncode != 0:
        return True  # fail safe: can't confirm "no new commits", so assume there are
    count = stdout.decode().strip()
    return count.isdigit() and int(count) > 0


async def _run_parallel(
    tasks: list[dict[str, Any]],
    sub_agent_manager: SubAgentManager,
) -> str:
    """Run several sub-agent tasks concurrently and return combined results.

    A single atomic call — useful for models that cannot reliably sequence N
    tool-call rounds. Each task gets its own scope clamp and runs blind to the
    others; a shared lock serializes any approval prompts back to the parent UI.

    A task with ``isolate_worktree: true`` runs inside its own git worktree
    (ADR-0068) instead of the shared working tree — opt-in, since fanning out
    concurrent *writes* onto one tree corrupts them into each other. `asyncio.gather`
    schedules each `run_single_agent` coroutine as its own `Task`, which copies
    `contextvars` at creation time, so each task's `active_worktree` is isolated
    from its siblings' — the same guarantee `enter_worktree`/`exit_worktree`
    already rely on for the single-agent path.
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

    parent_ui = get_current_ui() or StdUI()
    ui_lock = asyncio.Lock()

    async def run_single_agent(task_spec: dict[str, Any]) -> AgentTaskResult:
        agent_name = task_spec.get("agent_name", "")
        deliverable = task_spec.get("deliverable", "")
        task = task_spec.get("task", "")
        non_goals = task_spec.get("non_goals", []) or []
        additional_context = task_spec.get("additional_context", "")
        isolate = bool(task_spec.get("isolate_worktree", False))
        # _run_agent_task assigns the [agent_name #ordinal] label.
        buffered_ui = BufferedUI(
            parent_ui, shared_lock=ui_lock, session_id=get_current_tool_session()
        )

        worktree_path = ""
        base_sha = ""
        if isolate:
            # Captured before creating the worktree so cleanup can tell "clean
            # working tree" apart from "clean working tree but new commits
            # exist" — see `_worktree_has_new_commits`.
            base_sha = await _current_head_sha(os.getcwd())
            # A distinct name per task: enter_worktree's own default branch name
            # is second-granularity, which concurrent fan-out tasks can collide
            # on within the same second.
            branch_name = f"delegate-{agent_name}-{get_random_name(separator='-', add_random_digit=True)}"
            enter_msg = await enter_worktree(branch_name=branch_name)
            worktree_path = get_active_worktree()
            if not worktree_path:
                return AgentTaskResult(
                    buffered_ui.label or f"[{agent_name}]", None, enter_msg
                )

        result: AgentTaskResult | None = None
        try:
            result = await _run_agent_task(
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
            # Always attempt cleanup, including when the sub-agent errored —
            # this is what lets isolate_worktree survive a crashed sub-agent
            # rather than leaking worktrees (ADR-0068). Wrapped in its own
            # try/except: a cleanup failure (git missing, disk/lock issue)
            # must not escape into `asyncio.gather` and abort sibling tasks —
            # same best-effort posture as `_persist_subagent_history`.
            if isolate and worktree_path:
                try:
                    dirty = await _worktree_has_changes(worktree_path)
                    has_new_commits = await _worktree_has_new_commits(
                        worktree_path, base_sha
                    )
                    if dirty or has_new_commits:
                        # Real work exists (uncommitted or committed) — never
                        # force-delete it via exit_worktree's default
                        # keep_branch=False.
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

        # Reached only if the try block returned normally (an exception would
        # have propagated past this point after the finally block ran).
        assert result is not None
        return AgentTaskResult(
            buffered_ui.label or f"[{agent_name}]",
            result.result,
            result.error,
        )

    # return_exceptions=True is defense in depth, not the primary fix: cleanup
    # failures are already caught above so they surface as a result note, not
    # a raise. This guards against anything else genuinely unanticipated
    # (e.g. `_run_agent_task` itself raising) taking down every sibling task
    # instead of just the one that failed.
    raw_results = await asyncio.gather(
        *[run_single_agent(t) for t in tasks], return_exceptions=True
    )

    combined_results = []
    for spec, r in zip(tasks, raw_results):
        if isinstance(r, BaseException):
            label = f"[{spec.get('agent_name', '?')}]"
            combined_results.append(f"{label} Error: {r}")
            continue
        # r.agent_name already carries its [agent_name #ordinal] label.
        if not r.success:
            combined_results.append(f"{r.agent_name} Error: {r.error}")
        else:
            indented_result = "\n".join(
                ["  " + line for line in (r.result or "").splitlines()]
            )
            combined_results.append(f"{r.agent_name} completed:\n{indented_result}")
    return "\n\n".join(combined_results)


def create_delegate_to_agent_tool(
    sub_agent_manager: SubAgentManager | None = None,
):
    if sub_agent_manager is None:
        sub_agent_manager = default_sub_agent_manager
    agent_doc_section = agent_roster_doc(sub_agent_manager)

    async def delegate_to_agent(
        agent_name: str = "",
        deliverable: str = "",
        task: str = "",
        # Mutable defaults are intentional here: pydantic-ai builds a Pydantic v2
        # model from this signature and internally converts mutable defaults to
        # default_factory, so each tool call gets a fresh list. Using `= []`
        # instead of `list[str] | None = None` keeps the JSON schema compact
        # (avoids anyOf + null union that bloats every tool description sent to the LLM).
        non_goals: list[str] = [],  # noqa: B006
        additional_context: str = "",
        tasks: list[dict[str, Any]] = [],  # noqa: B006
    ) -> str:
        """See module docstring; required-arg signature is the scope clamp."""
        # FAN OUT: a non-empty `tasks` list runs several sub-agents concurrently
        # and returns their results together (one atomic call). Flat args are
        # ignored in that case.
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
        parent_ui = get_current_ui() or StdUI()
        # _run_agent_task assigns the [agent_name #ordinal] label (the panel
        # is the legend); no opaque per-instance id is shown to the user.
        buffered_ui = BufferedUI(parent_ui, session_id=get_current_tool_session())

        task_result = await _run_agent_task(
            agent_name=agent_name,
            deliverable=deliverable,
            non_goals=non_goals,
            task=task,
            additional_context=additional_context,
            sub_agent_manager=sub_agent_manager,
            ui=buffered_ui,
        )

        if not task_result.success:
            return f"Error: {task_result.error}"

        label = buffered_ui.label or f"[{agent_name}]"
        return f"{label} completed:\n\n{task_result.result}"

    setattr(delegate_to_agent, "zrb_is_delegate_tool", True)
    delegate_to_agent.__name__ = "DelegateToAgent"
    delegate_to_agent.__doc__ = (
        "Delegates a task to a named subagent for isolated execution.\n\n"
        "The envelope is the contract — a vague envelope comes back vague:\n"
        "- deliverable: concrete artifact that must exist on return (name the file, function, or decision).\n"
        "- task: how to produce it — reference exact files, line numbers, or commands when known.\n"
        "- non_goals: things the sub-agent must NOT do (scope clamp). Pass [] only when certain.\n\n"
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
    sub_agent_manager: SubAgentManager | None = None,
):
    if sub_agent_manager is None:
        sub_agent_manager = default_sub_agent_manager

    async def search_agent(query: str = "") -> str:
        agents = _delegatable_agents(sub_agent_manager)
        needle = query.strip().lower()
        if needle:
            agents = [
                a
                for a in agents
                if needle in a.name.lower() or needle in (a.description or "").lower()
            ]
        if not agents:
            return _no_agent_match_message(query)
        shown = agents[:_SEARCH_RESULT_LIMIT]
        lines = [f"- `{a.name}`: {a.description}" for a in shown]
        hidden = len(agents) - len(shown)
        if hidden > 0:
            lines.append(f"(+{hidden} more match — refine the query)")
        return "\n".join(lines)

    setattr(search_agent, "zrb_is_delegate_tool", True)
    search_agent.__name__ = "SearchAgent"
    # The roster is deliberately NOT embedded here: it is spelled out in the
    # delegation tools' docstrings, and this tool is the on-demand window onto
    # the part those docstrings truncate. Naming the truncation cap here would
    # pin a config value into a docstring that ships on every request.
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
