"""Find the task mistakes that make a declared task unreachable from the CLI.

Two failures share a symptom — a user types a task name, or watches one
vanish, and zrb has nothing to say about it:

- A task declared at the top level of a `zrb_init.py` and never registered
  (or referenced as an edge of a task that is). It is a live object with a
  name and no CLI word, so nothing ever runs it.
- Two of the user's own tasks share a name. `Group.add_task` replaces the
  earlier registration silently, by design, so the first one is simply gone.

Both are derived here from the init sources' namespaces and the finished
group tree. `Group` itself is not involved: shadowing a *built-in* is a
documented feature, not a mistake, and a rule that cannot tell that case from
a real duplicate would either nag on the feature or miss the bug.
"""

from __future__ import annotations

from types import ModuleType
from typing import Iterable, NamedTuple

from zrb.group.any_group import AnyGroup
from zrb.task.any_task import AnyTask

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


def find_task_diagnostics(
    declared: list[tuple[str, str, AnyTask]],
    root: AnyGroup,
    builtin_aliases: Iterable[str],
) -> list[TaskDiagnostic]:
    """Report declared-but-unreachable tasks and duplicate names.

    Args:
        declared: `(origin, symbol, task)` triples from `collect_declared_tasks`.
        root: The group tree as it stands after every init source loaded.
        builtin_aliases: Aliases the built-in tasks occupy, captured before
            init ran. Registering over one of these is the documented way to
            shadow a built-in, so it is not reported as a duplicate.
    """
    reachable = _reachable_tasks(root)
    by_name = _group_by_name(declared)
    builtins = set(builtin_aliases)
    # A built-in alias is the project's to shadow; only a name the built-ins
    # leave free can be a duplicate of the project's own making.
    duplicate_names = {
        name for name, entries in by_name.items() if len(entries) > 1 and name not in builtins
    }
    claimed = {id(task) for name in duplicate_names for _, _, task in by_name[name]}
    diagnostics = [
        _duplicate_diagnostic(name, by_name[name]) for name in sorted(duplicate_names)
    ]
    for origin, symbol, task in declared:
        # A task inside a duplicate group is best explained by the group: the
        # fix is the same rename, and the duplicate line already names it. A
        # second "and it is unreachable" line would only restate the shadowing.
        if id(task) in reachable or id(task) in claimed:
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
                    f"upstream, fallback, successor, or readiness check."
                ),
            )
        )
    return diagnostics


def _duplicate_diagnostic(
    name: str, entries: list[tuple[str, str, AnyTask]]
) -> TaskDiagnostic:
    """One line for a whole duplicate-name group, naming each declaration."""
    origins = {origin for origin, _, _ in entries}
    if len(origins) == 1:
        places = f"all declared in {next(iter(origins))}"
    else:
        places = "; ".join(f"{symbol!r} in {origin}" for origin, symbol, _ in entries)
    symbols = ", ".join(repr(symbol) for _, symbol, _ in entries)
    origin, symbol, task = entries[0]
    return TaskDiagnostic(
        symbol=symbol,
        origin=origin,
        task=task,
        problem="duplicate-name",
        detail=(
            f"{len(entries)} tasks are named {name!r} ({symbols}, {places}); "
            f"registering them all keeps only the last. Rename one, or pass a "
            f"distinct alias= to add_task."
        ),
    )


def _group_by_name(
    declared: list[tuple[str, str, AnyTask]],
) -> dict[str, list[tuple[str, str, AnyTask]]]:
    """Bucket declared tasks by name, counting each distinct object once."""
    by_name: dict[str, list[tuple[str, str, AnyTask]]] = {}
    seen: dict[str, set[int]] = {}
    for entry in declared:
        name = entry[2].name
        # The same object can be visible through several imports of it; it is
        # still one task, so a shared name must not read as a collision.
        if id(entry[2]) in seen.setdefault(name, set()):
            continue
        seen[name].add(id(entry[2]))
        by_name.setdefault(name, []).append(entry)
    return by_name


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
    return ids


def format_diagnostic(diagnostic: TaskDiagnostic) -> str:
    """One warning line, pointing at the source that has to change."""
    return f"{diagnostic.origin}: {diagnostic.detail}"