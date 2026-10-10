"""Find declared tasks the CLI cannot reach.

Reports two mistakes:

- A task declared at the top level of a `zrb_init.py` that is neither
  registered nor referenced as an edge of a task that is.
- Two of the project's own tasks registered under the same alias in one group
  (`Group.add_task` silently keeps the later one).

Collisions come from `Group.replacements`, not from grouping tasks by `name`:
aliases are per-group, and replacing a built-in is an intended shadow.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from types import ModuleType
from typing import TYPE_CHECKING, NamedTuple, cast

from zrb.group.any_group import AnyGroup
from zrb.group.group import Group, TaskReplacement
from zrb.task.any_task import AnyTask

if TYPE_CHECKING:
    from zrb.callback.any_callback import AnyCallback

# Edges that make a task reachable without a CLI word of its own.
_TASK_EDGES = ("upstreams", "fallbacks", "successors", "readiness_checks")


class TaskDiagnostic(NamedTuple):
    """One declared task, and why the CLI will not offer it as expected."""

    symbol: str
    origin: str
    task: AnyTask
    problem: str
    detail: str


def collect_declared_tasks(
    sources: Iterable[tuple[str, ModuleType]],
) -> list[tuple[str, str, AnyTask]]:
    """List the tasks each init source declares at module level.

    Returns `(origin, symbol, task)` per task. Only module attributes count.
    """
    declared: list[tuple[str, str, AnyTask]] = []
    for origin, module in sources:
        for symbol, value in vars(module).items():
            if isinstance(value, AnyTask):
                declared.append((origin, symbol, value))
    return declared


_builtin_task_ids: frozenset[int] = frozenset()


def snapshot_builtin_task_ids(root: AnyGroup) -> None:
    """Freeze the built-in task identities.

    Called once at `zrb` import, before any init source runs. `cli` is
    process-wide, so a later snapshot would count a previous run's project
    tasks as built-ins.
    """
    global _builtin_task_ids
    _builtin_task_ids = frozenset(id(task) for task in root.get_all_subtasks())


def get_builtin_task_ids() -> frozenset[int]:
    """The identities frozen by `snapshot_builtin_task_ids` (empty before it)."""
    return _builtin_task_ids


def reset_task_replacements(root: Group) -> None:
    """Drop the replacement log a previous `serve_cli` left on the tree."""
    for _, group in _collect_groups(root):
        group.replacements = []


def find_task_diagnostics(
    declared: list[tuple[str, str, AnyTask]],
    root: Group,
    builtin_task_ids: Iterable[int],
) -> list[TaskDiagnostic]:
    """Report unregistered tasks, then aliases two of the project's tasks share.

    Args:
        declared: `(origin, symbol, task)` triples from `collect_declared_tasks`.
        root: The group tree as it stands after every init source loaded.
        builtin_task_ids: Ids from `get_builtin_task_ids`; a task replacing one
            of these is a built-in shadow, not a collision.
    """
    builtin_ids = frozenset(builtin_task_ids)
    reachable = _reachable_tasks(root)
    declared_by_id = {id(task): (origin, symbol) for origin, symbol, task in declared}
    collisions, replaced_ids = _collisions(root, builtin_ids, declared_by_id)
    diagnostics = list(collisions)
    for origin, symbol, task in declared:
        # A displaced task is already named by its collision diagnostic.
        if id(task) in reachable or id(task) in replaced_ids:
            continue
        diagnostics.append(
            TaskDiagnostic(
                symbol=symbol,
                origin=origin,
                task=task,
                problem="unregistered",
                detail=(
                    f"task {task.name!r} (declared as {symbol!r}) is not registered "
                    f"and no task references it, so `zrb {task.name}` cannot reach "
                    f"it. Register it with cli.add_task(...), or make it an "
                    f"upstream, fallback, successor, readiness check, or a "
                    f"trigger's callback."
                ),
            )
        )
    return diagnostics


def _collisions(
    root: Group,
    builtin_ids: frozenset[int],
    declared_by_id: dict[int, tuple[str, str]],
) -> tuple[list[TaskDiagnostic], set[int]]:
    """One diagnostic per `(group, alias)` where a non-built-in was replaced.

    Also returns the replaced task ids.
    """
    diagnostics: list[TaskDiagnostic] = []
    replaced_ids: set[int] = set()
    for label, group in _collect_groups(root):
        by_alias: dict[str, list[TaskReplacement]] = {}
        for replacement in group.replacements:
            by_alias.setdefault(replacement.alias, []).append(replacement)
        for alias, replacements in by_alias.items():
            losers = _user_losers(replacements, builtin_ids)
            if not losers:
                continue
            replaced_ids.update(id(loser) for loser in losers)
            diagnostics.append(
                _collision_diagnostic(
                    alias, label, replacements[-1].replacement, losers, declared_by_id
                )
            )
    return diagnostics, replaced_ids


def _user_losers(
    replacements: list[TaskReplacement], builtin_ids: frozenset[int]
) -> list[AnyTask]:
    """The displaced tasks that are the project's own, in order, one each."""
    losers: list[AnyTask] = []
    for replacement in replacements:
        if id(replacement.replaced) in builtin_ids:
            continue
        if any(loser is replacement.replaced for loser in losers):
            continue
        losers.append(replacement.replaced)
    return losers


def _collision_diagnostic(
    alias: str,
    group_label: str,
    winner: AnyTask,
    losers: list[AnyTask],
    declared_by_id: dict[int, tuple[str, str]],
) -> TaskDiagnostic:
    winner_label = _describe_task(winner, declared_by_id)
    loser_labels = ", ".join(_describe_task(loser, declared_by_id) for loser in losers)
    return TaskDiagnostic(
        symbol=alias,
        origin=group_label,
        task=winner,
        problem="duplicate-alias",
        detail=(
            f"{alias!r} in {group_label} is registered by more than one task; "
            f"{winner_label} replaced {loser_labels}, so only the last stays "
            f"reachable. Rename one, or pass a distinct alias= to add_task."
        ),
    )


def _describe_task(task: AnyTask, declared_by_id: dict[int, tuple[str, str]]) -> str:
    """`'name' (declared as 'symbol' in origin)`, or just `'name'` if inline."""
    location = declared_by_id.get(id(task))
    if location is None:
        return repr(task.name)
    origin, symbol = location
    return f"{task.name!r} (declared as {symbol!r} in {origin})"


def _collect_groups(root: Group) -> Iterator[tuple[str, Group]]:
    """Every `Group` below *root* with a readable path; other `AnyGroup`s are skipped."""
    yield from _walk_groups(root, [])


def _walk_groups(group: Group, path: list[str]) -> Iterator[tuple[str, Group]]:
    label = "the root group" if not path else f"group {' '.join(path)}"
    yield label, group
    for alias, subgroup in group.subgroups.items():
        if isinstance(subgroup, Group):
            yield from _walk_groups(subgroup, path + [alias])


def _reachable_tasks(root: AnyGroup) -> set[int]:
    """Ids of every task the CLI can run: registered, or transitively an edge of one."""
    ids: set[int] = set()
    pending = list(root.get_all_subtasks())
    while pending:
        task = pending.pop()
        if id(task) in ids:
            continue
        ids.add(id(task))
        for edge in _TASK_EDGES:
            pending.extend(getattr(task, edge, None) or [])
        pending.extend(_callback_tasks(task))
    return ids


def _callback_tasks(task: AnyTask) -> Iterator[AnyTask]:
    """The tasks a trigger runs through its callbacks."""
    # `callbacks` (BaseTrigger) and `task` (Callback) are not on the protocols.
    callbacks = cast("list[AnyCallback]", getattr(task, "callbacks", None) or [])
    for callback in callbacks:
        wrapped = cast("AnyTask | None", getattr(callback, "task", None))
        if wrapped is not None:
            yield wrapped


def format_diagnostic(diagnostic: TaskDiagnostic) -> str:
    """One warning line, pointing at the source that has to change."""
    return f"{diagnostic.origin}: {diagnostic.detail}"
