from zrb.helper.string.conversion import to_cli_name
from zrb.helper.string.modification import double_quote
from zrb.helper.typecheck import typechecked
from zrb.helper.typing import List, Optional, TypeVar
from zrb.task.any_task import AnyTask

# flake8: noqa E501
TGroup = TypeVar("TGroup", bound="Group")


@typechecked
class Group:
    """
    Represents a group of tasks and subgroups, facilitating organization and hierarchy.

    This class allows the creation of a hierarchical structure by grouping tasks and
    other task groups together. It provides methods to add tasks, retrieve tasks,
    and generate Command-Line Interface (CLI) names based on group names.

    Attributes:
        name (str): The name of the group.
        description (str): The description of the group.
        parent (Optional[TGroup]): The parent group of the current group, if any.

    Examples:
        >>> from zrb import Group
        >>> system_group = Group(name='system')
        >>> log_group = Group(name='log', parent='system')
    """

    def __init__(
        self, name: str, description: str = "", parent: Optional[TGroup] = None
    ):
        self.__name = name
        self.__description = description
        self._parent = parent
        if parent is not None:
            parent.__children.append(self)
        self.__children: List[TGroup] = []
        self.__tasks: List[AnyTask] = []

    def get_parent(self) -> Optional[TGroup]:
        """
        Retrieves parent of the Group.

        Returns:
            Optional[Group]: Parent of the group.

        Examples:
            >>> from zrb import Group
            >>> system_group = Group(name='my system')
            >>> system_log_group = Group(name='log', parent=system_group)
            >>> print(system_group.get_parent())
            >>> print(system_log_group.get_parent())
            None
            <Group "my-system">
        """
        return self._parent

    def get_description(self) -> str:
        """
        Retrieves group description.

        Returns:
            str: Description of the group.

        Examples:
            >>> from zrb import Group
            >>> group = Group(name='group', description='description of the group')
            >>> print(group.get_description())
            description of the group
        """
        return self.__description

    def get_cli_name(self) -> str:
        """
        Retrieves the CLI name of the group, formatted in kebab case.

        The method converts the group name into a CLI-friendly format, suitable for command-line usage.

        Returns:
            str: The CLI name of the group.

        Examples:
            >>> from zrb import Group
            >>> system_group = Group(name='my system')
            >>> print(system_group.get_cli_name())
            my-system
        """
        return to_cli_name(self.__name)

    def _get_full_cli_name(self) -> str:
        """
        Retrieves the full CLI name of the group, including names of parent groups.

        This method is intended for internal use and constructs a full CLI name that reflects the group's hierarchy.

        Returns:
            str: The full CLI name of the group

        Examples:
            >>> from zrb import Group
            >>> system_group = Group(name='my system')
            >>> system_log_group = Group(name='log', parent=system_group)
            >>> print(system_log_group._get_full_cli_name())
            my-system log
        """
        cli_name = self.get_cli_name()
        if self._parent is None:
            return cli_name
        parent_cli_name = self._parent._get_full_cli_name()
        return f"{parent_cli_name} {cli_name}"

    def _add_task(self, task: AnyTask):
        """
        Adds a task to the group.

        This method is intended for internal use. It appends a given task to the  group's task list.

        Args:
            task (AnyTask): The task to be added.

        Examples:
            >>> from zrb import Group, Task
            >>> first_task = Task(name='first-task')
            >>> second_task = Task(name='second-task')
            >>> group = Group(name='group')
            >>> group._add_task(first_task)
            >>> group._add_task(second_task)
            >>> print(group.get_tasks())
            [<Task "group first-task">, <Task "group second-task">]
        """
        self.__tasks.append(task)

    def get_tasks(self) -> List[AnyTask]:
        """
        Get direct Tasks under this Task Group.

        Returns:
            List[AnyTask]: List of direct Tasks under this Task Group.

        Examples:
            >>> from zrb import Group, Task
            >>> group = Group(name='group')
            >>> first_task = Task(name='first-task', group=group)
            >>> second_task = Task(name='second-task', group=group)
            >>> print(group.get_tasks())
            [<Task "group first-task">, <Task "group second-task">]
        """
        return self.__tasks

    def get_children(self) -> List[TGroup]:
        """
        Retrieves the list of direct subgroups under this group.

        Returns a list of immediate subgroups nested within this group, helping to understand the group's hierarchical structure.

        Returns:
            List[Group]: List of direct subgroups under this Task group.

        Examples:
            >>> from zrb import Group, Task
            >>> group = Group(name='group')
            >>> sub_group_1 = TaskGroup(name='sub-group-1', parent=group)
            >>> sub_group_2 = TaskGroup(name='sub-group-2', parent=group)
            >>> print(group.get_children())
            [<Group "group sub-group-1">, <Group "group sub-group-2">]
        """
        return self.__children

    def __repr__(self) -> str:
        cls_name = self.__class__.__name__
        full_cli_name = double_quote(self._get_full_cli_name())
        return f"<{cls_name} {full_cli_name}>"
