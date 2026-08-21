from abc import ABC, abstractmethod

from zrb.task.any_task import AnyTask


class NodeNotFoundError(ValueError):
    pass


class AnyGroup(ABC):
    """A CLI command group: a namespace holding tasks and nested subgroups.

    Groups form the `zrb <group> <subgroup> <task>` command tree. Each entry is
    registered under an *alias* — the word typed on the CLI — which defaults to
    the task's or group's own name but can differ, so the same task can appear
    in more than one place.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Group name"""
        pass

    @property
    @abstractmethod
    def banner(self) -> str:
        """Group banner"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Group description"""
        pass

    @property
    @abstractmethod
    def subtasks(self) -> dict[str, AnyTask]:
        """Group subtasks"""
        pass

    @property
    @abstractmethod
    def subgroups(self) -> "dict[str, AnyGroup]":
        """Group subgroups"""
        pass

    @abstractmethod
    def add_group(self, group: "AnyGroup", alias: str | None = None) -> "AnyGroup":
        """Register a subgroup under this one.

        Args:
            group: The group to nest.
            alias: CLI word addressing it. Defaults to the group's own name.

        Returns:
            The group that was added, so calls can be chained.
        """

    @abstractmethod
    def add_task(self, task: "AnyTask", alias: str | None = None) -> "AnyTask":
        """Register a task in this group.

        Args:
            task: The task to expose.
            alias: CLI word addressing it. Defaults to the task's own name.

        Returns:
            The task that was added, so calls can be chained.
        """

    @abstractmethod
    def remove_group(self, group: "AnyGroup | str"):
        """Unregister a subgroup, by alias or by the group object itself.

        Passing the group object removes it under every alias it is registered
        as; passing an alias removes only that one.

        Raises:
            ValueError: If the group is not registered here.
        """

    @abstractmethod
    def remove_task(self, task: "AnyTask | str"):
        """Unregister a task, by alias or by the task object itself.

        Passing the task object removes it under every alias it is registered
        as; passing an alias removes only that one.

        Raises:
            ValueError: If the task is not registered here.
        """

    @abstractmethod
    def get_task_by_alias(self, alias: str) -> AnyTask | None:
        """Look up a directly-registered task, or None if the alias is unknown.

        Does not search subgroups.
        """

    @abstractmethod
    def get_group_by_alias(self, alias: str) -> "AnyGroup | None":
        """Look up a directly-registered subgroup, or None if the alias is unknown.

        Does not search recursively.
        """

    @abstractmethod
    def get_node_path(self, node: "AnyGroup | AnyTask") -> list[str] | None:
        """Get the path (aliases) from this group down to *node*, or None.

        Args:
            node: The target node.

        Returns:
            A list of aliases representing the path to the node, or None if
            the node is not found.
        """

    @abstractmethod
    def get_subtasks(self, web_only: bool = False) -> dict[str, AnyTask]:
        """Get the direct subtasks of this group.

        Args:
            web_only: If True, only include tasks that are not CLI-only.
        """

    @abstractmethod
    def get_all_subtasks(self, web_only: bool = False) -> list[AnyTask]:
        """Get all subtasks (including nested ones) within this group's hierarchy.

        Args:
            web_only: If True, only include tasks that are not CLI-only.
        """

    @abstractmethod
    def get_non_empty_subgroups(self, web_only: bool = False) -> "dict[str, AnyGroup]":
        """Get subgroups that contain at least one task.

        Args:
            web_only: If True, only consider tasks that are not CLI-only.
        """

    @abstractmethod
    def extract_node(
        self, args: list[str], web_only: bool = False
    ) -> "tuple[AnyGroup | AnyTask, list[str], list[str]]":
        """Extract a node (Group or Task) from a list of command-line arguments,
        starting the search from this group.

        Args:
            args: The list of command-line arguments.
            web_only: If True, only consider tasks that are not CLI-only.

        Returns:
            A tuple containing the extracted node, the path to the node, and
            any residual arguments.

        Raises:
            NodeNotFoundError: If no matching task or group is found for a
                given argument.
        """
