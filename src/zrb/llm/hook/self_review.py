"""The built-in self-review gate — a synchronous Stop hook, registered only
while `LLM_SELF_REVIEW_ENABLED` is on.

On a turn that changed files, a reviewer agent reads what the turn changed —
the working tree diffed against its state at turn start — with a fresh
context (not the author's transcript) and read-only tools. A
`Request changes` verdict blocks the Stop (`session_extension.py`'s
block-to-continue), so the main agent checks the findings and fixes the real
ones before answering; `LGTM`, a failed review, or an unclear verdict lets the
turn end. `LLM_SELF_REVIEW_MAX_ROUNDS` caps consecutive blocking reviews.
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
from zrb.util.git.snapshot_command import SnapshotError
from zrb.util.git.snapshot_listing import get_fork_point
from zrb.util.git.snapshot_store import Snapshot, SnapshotStore
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
    """The gate itself. It counts a run's consecutive blocking reviews — per
    run, since concurrent sessions share one hook manager. A run has an entry
    only while the gate is holding its turn open: any review that lets the
    turn end removes it, and a turn's first Stop (`stop_hook_active` still
    false) restarts it, so a turn cancelled mid-continuation leaves at most
    one entry for its run, cleared by that run's next turn.

    A delegated sub-agent's run is not reviewed: its changes land in the
    parent's working directory, or in a worktree under it, which the parent's
    own review diffs against a snapshot taken before it delegated. Reviewing each sub-agent too would
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
            rounds.pop(run, None)
            return HookResult(output="Self-review skipped: round limit reached.")
        result = await _review(context, payload)
        if result.modifications.get("decision") == "block":
            rounds[run] = rounds.get(run, 0) + 1
        else:
            rounds.pop(run, None)
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
    #: Files git could not read at Stop: listed, but not diffed, since an
    #: unread file would otherwise read as deleted.
    unreadable: list[str] = dataclasses.field(default_factory=list)


def _resolve_scope(payload: dict[str, Any], deadline: float) -> _Scope:
    """What the turn changed: the working directory diffed from its
    turn-start snapshot to its state now — every repository under it, nested
    ones and linked worktrees included (`util/git/snapshot_listing.py`). That
    covers edits made through `Shell` and changes committed mid-turn, and
    leaves out the user's earlier uncommitted work. Paths the file tools named
    that the diff does not cover — ignored, or outside the working directory
    — are listed too. Every git command stops at *deadline*.

    When the snapshot failed there is no diff, only the file tools' paths:
    diffing those against HEAD instead would hand the reviewer the user's
    earlier uncommitted work."""
    tool_paths = [p for p in payload.get("changed_paths") or [] if isinstance(p, str)]
    changes = _diff_turn(payload.get("turn_start_snapshot"), deadline)
    root, paths, diff, unreadable = changes or ("", [], "", [])
    changed = [os.path.join(root, *path.split("/")) for path in paths]
    covered = {os.path.normcase(path) for path in changed}
    uncovered = [
        _absolute(p)
        for p in tool_paths
        if os.path.normcase(_absolute(p)) not in covered
    ]
    return _Scope(
        [_display(p) for p in changed + uncovered],
        diff,
        [_display(os.path.join(root, *p.split("/"))) for p in unreadable],
    )


def _diff_turn(
    start: Any, deadline: float
) -> tuple[str, list[str], str, list[str]] | None:
    """The working directory's `(root, changed paths, diff, unreadable
    paths)` since the turn-start snapshot *start*, or None when there is none
    to diff."""
    if not isinstance(start, dict):
        return None
    workdir, before, git_dir = (
        start.get("workdir"),
        start.get("tree"),
        start.get("store"),
    )
    if not (
        isinstance(workdir, str)
        and isinstance(before, str)
        and isinstance(git_dir, str)
    ):
        return None
    store = SnapshotStore.open_temporary(git_dir, workdir)
    try:
        after = store.snapshot(deadline)
        before = _with_new_repositories(store, before, after, deadline)
        # A file unreadable at Stop is not in *after*; taken out of *before*
        # too, it is listed as unreadable rather than read as deleted.
        before = store.create_tree_without(before, after.unreadable, deadline)
        paths, diff = store.diff(before, after.tree, deadline)
    except (SnapshotError, OSError) as e:
        CFG.LOGGER.debug(f"Self-review could not diff {workdir}: {e}")
        return None
    return store.work_tree, paths, _truncate(diff), list(after.unreadable)


def _with_new_repositories(
    store: SnapshotStore, before: str, after: Snapshot, deadline: float
) -> str:
    """*before*, with each nested repository that appeared during the turn —
    a worktree `EnterWorktree` created, a clone — as it stood at the commit
    it started from, so the diff shows what the turn changed in it rather
    than its whole checkout. One with no commit yet stays out of *before*:
    all of it is new."""
    for repository in after.repositories:
        if not repository:
            continue
        listed = store.git(
            ["ls-tree", "--name-only", before, "--", repository], deadline=deadline
        )
        if listed.strip():
            continue
        fork = get_fork_point(
            os.path.join(store.work_tree, *repository.split("/")), deadline
        )
        if fork is not None:
            before = store.create_repository_baseline(
                before, after, repository, fork, deadline
            )
    return before


def _absolute(path: str) -> str:
    """*path* resolved as the file tools resolve it: `~` expanded."""
    return os.path.realpath(os.path.expanduser(path))


def _display(path: str) -> str:
    """*path* relative to the working directory when inside it, else absolute."""
    cwd = os.path.realpath(os.getcwd())
    try:
        rel = os.path.relpath(path, cwd)
    except ValueError:  # another drive on Windows
        return path
    if rel == os.pardir or rel.startswith(os.pardir + os.sep):
        return path
    return rel.replace(os.sep, "/")


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
    unreadable = "".join(f"\n- {path}" for path in scope.unreadable)
    unreadable_block = (
        f"\n\nGit could not read these files, so they are not diffed:{unreadable}"
        if unreadable
        else ""
    )
    return (
        f"This turn changed these files:\n\n{listing}\n\n{diff_block}\n\n"
        "A listed file with no hunk above is ignored by git or outside the "
        f"working directory: read it directly.{unreadable_block}"
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
