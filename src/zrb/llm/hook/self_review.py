"""The built-in self-review gate — a synchronous Stop hook, registered only
while `LLM_SELF_REVIEW_ENABLED` is on.

On a turn that changed files, a reviewer agent reads what the turn changed —
the working tree diffed against its state at turn start — with a fresh
context (not the author's transcript) and read-only tools. A
`Request changes` verdict blocks the Stop (`session_extension.py`'s
block-to-continue), so the main agent checks the findings and fixes the real
ones before answering; `LGTM`, a failed review, or an unclear verdict lets the
turn end. `LLM_SELF_REVIEW_MAX_ROUNDS` caps the reviews per user turn.
"""

import asyncio
import dataclasses
import os
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from zrb.config.config import CFG
from zrb.llm.hook.agent_hook_registry import get_agent_hook_builder
from zrb.llm.hook.interface import HookCallable, HookContext, HookResult
from zrb.llm.hook.schema import AgentHookConfig, HookConfig
from zrb.llm.hook.types import HookEvent, HookType
from zrb.llm.prompt.prompt import get_prompt
from zrb.util.git.snapshot_store import SnapshotError, SnapshotStore
from zrb.util.truncate import truncate_text

if TYPE_CHECKING:
    from zrb.llm.hook.manager import HookManager

_NAME = "self-review"
#: Slack for the executor's own timeout past the hook's deadline.
_EXECUTOR_GRACE_SECONDS = 30
_REVIEWER_TOOLS = ["Read", "Grep", "Glob"]
_BLOCK_PREFIX = (
    "[SELF-REVIEW] An independent reviewer read this turn's changes and "
    "reported the findings below. Check each one against the code: fix the "
    "real defects, with a test where one applies, and say briefly why any "
    "finding is not a defect. Then give your complete final answer again — it "
    "replaces the previous one."
)


def register_self_review_hook(manager: "HookManager") -> None:
    """Hook factory: register the gate on *manager* when it is switched on."""
    if not CFG.LLM_SELF_REVIEW_ENABLED:
        return
    config = HookConfig(
        name=_NAME,
        events=[HookEvent.STOP],
        type=HookType.AGENT,
        config=AgentHookConfig(
            system_prompt=get_prompt("self_review"), tools=_REVIEWER_TOOLS
        ),
        # The hook enforces `LLM_SELF_REVIEW_TIMEOUT` itself: its git
        # commands are cut off at the deadline, and the reviewer is cancelled
        # inside the hook's own event loop, where cancelling reaches its model
        # request. The executor's timeout only abandons the worker thread, so
        # it is set past that deadline and never fires first.
        timeout=CFG.LLM_SELF_REVIEW_TIMEOUT + _EXECUTOR_GRACE_SECONDS,
    )
    manager.add_hook(create_self_review_hook(), [HookEvent.STOP], config)


def create_self_review_hook() -> HookCallable:
    """The gate itself. It counts blocking rounds per run — concurrent
    sessions share one hook manager — and a run's count restarts on each user
    turn's first Stop, the one where `stop_hook_active` is still false; a run
    never blocked keeps no entry.

    A delegated sub-agent's run is not reviewed: its changes land in the
    parent's working tree, which the parent's own review diffs against a
    snapshot taken before it delegated. Reviewing each sub-agent too would
    multiply reviewer runs, and a sub-agent's diff would include whatever its
    parallel siblings changed."""
    rounds: dict[str, int] = {}

    async def self_review(context: HookContext) -> HookResult:
        payload = context.event_data if isinstance(context.event_data, dict) else {}
        if payload.get("nested_run"):
            return HookResult(
                output="Self-review skipped: a delegated sub-agent's run; the "
                "parent's review covers its changes."
            )
        run = str(payload.get("run_scope") or "")
        if not context.stop_hook_active:
            rounds.pop(run, None)
        if rounds.get(run, 0) >= CFG.LLM_SELF_REVIEW_MAX_ROUNDS:
            return HookResult(output="Self-review skipped: round limit reached.")
        result = await _review(context, payload)
        if result.modifications.get("decision") == "block":
            rounds[run] = rounds.get(run, 0) + 1
        return result

    return self_review


async def _review(context: HookContext, payload: dict[str, Any]) -> HookResult:
    """One review of the turn in *payload*: a block carrying the findings, or
    a pass-through result saying why the turn may end."""
    deadline = time.monotonic() + CFG.LLM_SELF_REVIEW_TIMEOUT
    # Not wrapped in `wait_for`: cancelling cannot stop a worker thread,
    # and `asyncio.run` waits for it on exit anyway. The deadline stops
    # its git commands instead.
    scope = await asyncio.to_thread(_resolve_scope, payload, deadline)
    if time.monotonic() >= deadline:
        return _timed_out()
    if not scope.paths:
        return HookResult(output="Self-review skipped: no files changed.")
    try:
        report = await asyncio.wait_for(
            _run_reviewer(context, scope),
            timeout=max(deadline - time.monotonic(), 0),
        )
    except asyncio.TimeoutError:
        return _timed_out()
    if report is None or _verdict(report) != "request changes":
        return HookResult(output=report or "Self-review produced no report.")
    return HookResult.block(f"{_BLOCK_PREFIX}\n\n{report.strip()}")


def _timed_out() -> HookResult:
    CFG.LOGGER.warning(
        "Self-review timed out after %ss, not blocking.",
        CFG.LLM_SELF_REVIEW_TIMEOUT,
    )
    return HookResult(output="Self-review skipped: timed out.")


@dataclass
class _Scope:
    paths: list[str]
    diff: str


def _resolve_scope(payload: dict[str, Any], deadline: float) -> _Scope:
    """What the turn changed: the working directory's tree at turn start
    diffed against its tree now, which covers edits made through `Shell` and
    changes committed mid-turn, and leaves out the user's earlier uncommitted
    work. Paths the file tools named that this diff does not cover — ignored,
    or outside the directory — are listed too. Every git command stops at
    *deadline*.

    Without both snapshots (one failed) only the file tools' paths are listed,
    with no diff: diffing them against HEAD would hand the reviewer the user's
    earlier uncommitted work too."""
    tool_paths = [p for p in payload.get("changed_paths") or [] if isinstance(p, str)]
    start = payload.get("turn_start_snapshot")
    before = start.get("tree") if isinstance(start, dict) else None
    git_dir = start.get("store") if isinstance(start, dict) else None
    if not (isinstance(before, str) and isinstance(git_dir, str)):
        return _Scope(tool_paths, "")
    store = SnapshotStore.open_temporary(git_dir, os.getcwd())
    try:
        after, _ = store.snapshot(deadline)
        tree_paths, diff = store.diff(before, after, deadline)
    except SnapshotError as e:
        CFG.LOGGER.debug(f"Self-review could not diff the turn: {e}")
        return _Scope(tool_paths, "")
    root = store.work_tree
    uncovered = [p for p in tool_paths if _tree_relative(p, root) not in tree_paths]
    return _Scope(tree_paths + uncovered, _truncate(diff))


def _tree_relative(path: str, root: str) -> str:
    """*path* as the tree diff names it: relative to the store's work tree.
    The file tools expand `~`, so a tool path is expanded the same way."""
    absolute = os.path.realpath(os.path.expanduser(path))
    return os.path.relpath(absolute, root).replace(os.sep, "/")


async def _run_reviewer(context: HookContext, scope: _Scope) -> str | None:
    """The reviewer's report, or None when no review happened — a failed or
    unavailable review must never hold the author's turn hostage.

    The reviewer is an ordinary agent hook built through the registration
    seam `hook.manager` uses too, handed the review request instead of the
    author's transcript as its input.
    """
    builder = get_agent_hook_builder()
    if builder is None:
        CFG.LOGGER.warning(
            "Self-review skipped: zrb.llm.agent was never imported in this process."
        )
        return None
    reviewer = builder(
        AgentHookConfig(
            system_prompt=get_prompt("self_review"),
            tools=_REVIEWER_TOOLS,
            model=CFG.LLM_SELF_REVIEW_MODEL or None,
        )
    )
    result = await reviewer(
        dataclasses.replace(context, event_data=_create_review_request(scope))
    )
    if not result.success:
        CFG.LOGGER.warning(f"Self-review failed, not blocking: {result.output}")
        return None
    return result.output


def _create_review_request(scope: _Scope) -> str:
    listing = "\n".join(f"- {path}" for path in scope.paths)
    diff_block = (
        f"Diff against the start of this turn:\n\n```diff\n{scope.diff}\n```"
        if scope.diff
        else "No diff of this turn's changes is available."
    )
    return (
        f"This turn changed these files:\n\n{listing}\n\n{diff_block}\n\n"
        "A listed file with no hunk above is untracked, ignored by git, outside "
        "the repository, or already committed: read it directly."
    )


def _truncate(diff: str) -> str:
    truncated, _ = truncate_text(diff, CFG.LLM_MAX_OUTPUT_CHARS)
    return truncated


def _verdict(report: Any) -> str:
    """The report's closing verdict line, lowercased, with markdown and a
    leading `Verdict:` label stripped."""
    for line in reversed(str(report).strip().splitlines()):
        stripped = line.strip().strip("*_`#> ").strip().rstrip(".").lower()
        stripped = stripped.removeprefix("verdict:").strip().strip("*_` ")
        if stripped:
            return stripped
    return ""
