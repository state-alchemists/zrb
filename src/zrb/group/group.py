"""CLI command grouping — the nodes between `zrb` and a task.

A `Group` is one word in a command line. Nesting groups nests the words, so
`cli.add_group(Group("db")).add_task(migrate_task)` is reached as
`zrb db migrate`. Groups hold subgroups and tasks under *aliases*, which is how
the same task object can appear under two names without being redefined.
"""

from typing import Any, TypeVar

from zrb.group.any_group import AnyGroup, NodeNotFoundError
from zrb.task.any_task import AnyTask

_T = TypeVar("_T", bound=AnyTask)


class Group(AnyGroup):
    """A named node in the CLI tree, holding subgroups and tasks.

    Register it on the `cli` singleton (or on another group) and it becomes a
    command word:

        from zrb import cli, Group, Task

        db = cli.add_group(Group("db", description="Database chores"))
        db.add_task(Task(name="migrate", action=lambda ctx: ...))
        # -> zrb db migrate

    `subgroups` and `subtasks` are returned alphabetically by alias, which is
    what makes `--help` output stable rather than insertion-ordered.
    """

    def __init__(
        self, name: str, description: str | None = None, banner: str | None = None
    ):
        """Define a CLI command group.

        Args:
            name: Group name, used as the CLI word addressing it.
            description: Help text. Defaults to `name`.
            banner: Text printed above the group's help listing.
        """
        self._name = name
        self._banner = banner
        self._description = description
        self._groups: dict[str, AnyGroup] = {}
        self._tasks: dict[str, AnyTask] = {}

    def __repr__(self):
        return f"<{self.__class__.__name__} name={self._name}>"

    @property
    def name(self) -> str:
        """The group's name, as typed on the CLI."""
        return self._name

    @property
    def banner(self) -> str:
        """Text printed above this group's help listing, or `""` if unset."""
        if self._banner is None:
            return ""
        return self._banner

    @property
    def description(self) -> str:
        """Help text for this group. Falls back to `name` when unset."""
        return self._description if self._description is not None else self.name

    @property
    def subgroups(self) -> dict[str, AnyGroup]:
        """Registered subgroups keyed by alias, sorted by alias."""
        names = list(self._groups.keys())
        names.sort()
        return {name: self._groups[name] for name in names}

    @property
    def subtasks(self) -> dict[str, AnyTask]:
        """Registered tasks keyed by alias, sorted by alias."""
        alias = list(self._tasks.keys())
        alias.sort()
        return {name: self._tasks[name] for name in alias}

    def add_group(self, group: "AnyGroup | str", alias: str | None = None) -> AnyGroup:
        """Register *group* as a subgroup and return it, so calls can chain.

        Args:
            group: The group to register. A plain string is shorthand for
                `Group(that_string)`.
            alias: CLI word addressing it. Defaults to the group's own name;
                pass one to expose the same group under a second word.

        Returns:
            The registered group — the newly built one when *group* was a
            string, otherwise *group* itself.
        """
        real_group = Group(group) if isinstance(group, str) else group
        alias = alias if alias is not None else real_group.name
        self._groups[alias] = real_group
        return real_group

    def add_task(self, task: _T, alias: str | None = None) -> _T:
        """Register *task* under this group and return it, so calls can chain.

        Args:
            task: The task to expose.
            alias: CLI word addressing it. Defaults to the task's own name;
                pass one to expose the same task object twice.

        Returns:
            *task*, unchanged.
        """
        alias = alias if alias is not None else task.name
        self._tasks[alias] = task
        return task

    def _remove_registered(
        self, items: dict[str, Any], target: Any, item_type: type, label: str
    ) -> dict[str, Any]:
        """Shared object/alias/name removal logic for remove_group/remove_task.

        A string `target` is matched against aliases first and against
        registered-item *names* second, so an alias always wins when the two
        disagree.

        Raises:
            ValueError: Nothing matched, so the call would silently do nothing.
        """
        original_len = len(items)
        if isinstance(target, item_type):
            new_items = {
                alias: existing
                for alias, existing in items.items()
                if target != existing
            }
            if len(new_items) == original_len:
                raise ValueError(f"Cannot remove {label} {target} from {self}")
            return new_items
        # target is string, try to remove by alias
        new_items = {
            alias: existing for alias, existing in items.items() if alias != target
        }
        if len(new_items) < original_len:
            return new_items
        # if alias removal didn't work, try to remove by name
        new_items = {
            alias: existing
            for alias, existing in items.items()
            if existing.name != target
        }
        if len(new_items) < original_len:
            return new_items
        raise ValueError(f"Cannot remove {label} {target} from {self}")

    def remove_group(self, group: "AnyGroup | str"):
        """Unregister a subgroup, by object, by alias, or by name.

        A string is matched against aliases first and against group *names*
        second, so an alias always wins when the two disagree.

        Raises:
            ValueError: Nothing matched, so the call would silently do nothing.
        """
        self._groups = self._remove_registered(self._groups, group, AnyGroup, "group")

    def remove_task(self, task: "AnyTask | str"):
        """Unregister a task, by object, by alias, or by name.

        A string is matched against aliases first and against task *names*
        second, so an alias always wins when the two disagree.

        Raises:
            ValueError: Nothing matched, so the call would silently do nothing.
        """
        self._tasks = self._remove_registered(self._tasks, task, AnyTask, "task")

    def get_task_by_alias(self, alias: str) -> AnyTask | None:
        """The task registered under *alias*, or None. Does not search names."""
        return self._tasks.get(alias)

    def get_group_by_alias(self, alias: str) -> AnyGroup | None:
        """The subgroup registered under *alias*, or None. Does not search names."""
        return self._groups.get(alias)

    def get_node_path(self, node: "AnyGroup | AnyTask") -> list[str] | None:
        """Get the path (aliases) from this group down to *node*, or None."""
        if self == node:
            return [self.name]
        if isinstance(node, AnyTask):
            for alias, subtask in self.subtasks.items():
                if subtask == node:
                    return [alias]
        if isinstance(node, AnyGroup):
            for alias, subgroup in self.subgroups.items():
                if subgroup == node:
                    return [alias]
        for alias, subgroup in self.subgroups.items():
            result = subgroup.get_node_path(node)
            if result is not None:
                return [alias] + result
        return None

    def get_subtasks(self, web_only: bool = False) -> dict[str, AnyTask]:
        """Get the direct subtasks of this group."""
        return {
            alias: subtask
            for alias, subtask in self.subtasks.items()
            if not web_only or (web_only and not subtask.cli_only)
        }

    def get_all_subtasks(self, web_only: bool = False) -> list[AnyTask]:
        """Get all subtasks (including nested ones) within this group's hierarchy."""
        subtasks = [
            subtask
            for subtask in self.subtasks.values()
            if not web_only or (web_only and not subtask.cli_only)
        ]
        for subgroup in self.subgroups.values():
            subtasks += subgroup.get_all_subtasks(web_only)
        return subtasks

    def get_non_empty_subgroups(self, web_only: bool = False) -> dict[str, AnyGroup]:
        """Get subgroups that contain at least one task."""
        return {
            alias: subgroup
            for alias, subgroup in self.subgroups.items()
            if len(subgroup.get_all_subtasks(web_only)) > 0
        }

    def extract_node(
        self, args: list[str], web_only: bool = False
    ) -> "tuple[AnyGroup | AnyTask, list[str], list[str]]":
        """Extract a node (Group or Task) from a list of command-line arguments,
        starting the search from this group.

        Raises:
            NodeNotFoundError: If no matching task or group is found for a
                given argument.
        """
        node: "AnyGroup | AnyTask" = self
        node_path = []
        residual_args = []
        for index, name in enumerate(args):
            task = node.get_task_by_alias(name)
            if web_only and task is not None and task.cli_only:
                task = None
            group = node.get_group_by_alias(name)
            # Only ignore empty groups if web_only is True
            if (
                group is not None
                and web_only
                and len(group.get_all_subtasks(web_only)) == 0
            ):
                group = None
            if task is None and group is None:
                raise NodeNotFoundError(
                    f"Invalid subcommand: {self.name} {' '.join(args)}"
                )
            node_path.append(name)
            if group is not None:
                if task is not None and index == len(args) - 1:
                    node = task
                    residual_args = args[index + 1 :]
                    break
                node = group
                continue
            if task is not None:
                node = task
                residual_args = args[index + 1 :]
                break
        return node, node_path, residual_args
