"""Find the task mistakes that make a declared task unreachable from the CLI.

Two failures share a symptom — a user types a task name, or watches one
vanish, and zrb has nothing to say about it:

- A task declared at the top level of a `zrb_init.py` and never registered
  (or referenced as an edge of a task that is). It is a live object with a
  name and no CLI word, so nothing ever runs it.
- Two of the project's own tasks registered under the same alias in the same
  group. `Group.add_task` replaces the earlier one silently, by design, so the
  first is gone.

Collisions are read from the replacement log `Group.add_task` keeps, not by
grouping declared tasks by `name`: an alias is a per-group word, and the same
task object may be exposed under several. Two tasks that share a name but sit
under distinct aliases are a valid configuration, not a collision. Shadowing a
*built-in* is likewise intended, so a replacement whose victim is a built-in
object the pre-init tree already held is left quiet.
"""

from __future__ import annotations

from types import ModuleType
from typing import TYPE_CHECKING, Iterable, Iterator, NamedTuple, cast

from zrb.group.any_group import AnyGroup
from zrb.group.group import Group, TaskReplacement
from zrb.task.any_task import AnyTask

if TYPE_CHECKING:
    from zrb.callback.any_callback import AnyCallback

# The edges through which one task pulls in another. A task referenced here is
# reachable even with no CLI word of its own: that is how a readiness check or
# a fallback stays alive without being registered.
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

    Returns `(origin, symbol, task)` per task. Only module attributes count,
    so a task built inside a function or a factory body is not reported — it
    was never on track to become a CLI word.
    """
    declared: list[tuple[str, str, AnyTask]] = []
    for origin, module in sources:
        for symbol, value in vars(module).items():
            if isinstance(value, AnyTask):
                declared.append((origin, symbol, value))
    return declared


_builtin_task_ids: frozenset[int] = frozenset()


def snapshot_builtin_task_ids(root: AnyGroup) -> None:
    """Freeze the built-in task identities once, as the built-ins register.

    Read once at `zrb` package import, when the built-ins have registered but
    no init source has run, rather than on every `serve_cli`. `cli` is a
    process-wide tree that keeps what each run registers on it, so reading it
    later would count a previous run's project tasks as built-ins and silence
    a collision that should warn.
    """
    global _builtin_task_ids
    _builtin_task_ids = frozenset(id(task) for task in root.get_all_subtasks())


def get_builtin_task_ids() -> frozenset[int]:
    """The identities frozen by `snapshot_builtin_task_ids` (empty before it)."""
    return _builtin_task_ids


def reset_task_replacements(root: Group) -> None:
    """Drop the replacement log a previous startup left on the tree.

    `cli` is a process-wide singleton, so a second `serve_cli` in one process
    (tests) would otherwise re-read and re-report the first run's collisions.
    """
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
        # A collision's displaced task is gone from the tree too, but the
        # collision line names it; a second "unreachable" line would only
        # restate the replacement under a wrong cause.
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
    """One diagnostic per `(group, alias)` the project's own tasks collided on.

    A replacement is a collision only when its victim is not a built-in. The
    victim list and its id set come back together, since `find_task_diagnostics`
    uses the ids to suppress a duplicate "unregistered" line.
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
    """Every `Group` below *root*, with a human-readable path for each.

    Third-party `AnyGroup` implementations are skipped: the replacement log
    lives on `Group`, and one without it never recorded a collision to report.
    """
    yield from _walk_groups(root, [])


def _walk_groups(group: Group, path: list[str]) -> Iterator[tuple[str, Group]]:
    label = "the root group" if not path else f"group {' '.join(path)}"
    yield label, group
    for alias, subgroup in group.subgroups.items():
        if isinstance(subgroup, Group):
            yield from _walk_groups(subgroup, path + [alias])


def _reachable_tasks(root: AnyGroup) -> set[int]:
    """Ids of every task the CLI can run: registered, or an edge of one.

    Walks the graph transitively, so a readiness check's own upstream counts
    as reachable even when nothing else names it.
    """
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
    """The tasks *task* runs through its callbacks.

    A trigger fires its `Callback`s on every event, so a task reached only that
    way runs without a CLI word or an edge of its own — it must not be
    reported as unreachable.
    """
    # `callbacks` belongs to `BaseTrigger`, and `task` to `Callback`: neither is
    # on `AnyTask`, so both are read off the object, as the edge walk does. A
    # third-party callback with no `task` has nothing to follow.
    callbacks = cast("list[AnyCallback]", getattr(task, "callbacks", None) or [])
    for callback in callbacks:
        wrapped = cast("AnyTask | None", getattr(callback, "task", None))
        if wrapped is not None:
            yield wrapped


def format_diagnostic(diagnostic: TaskDiagnostic) -> str:
    """One warning line, pointing at the source that has to change."""
    return f"{diagnostic.origin}: {diagnostic.detail}"
