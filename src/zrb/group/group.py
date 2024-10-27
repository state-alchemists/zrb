from collections.abc import Mapping
from .any_group import AnyGroup
from ..task.any_task import AnyTask


class Group(AnyGroup):

    def __init__(
        self, name: str, description: str | None = None, banner: str | None = None
    ):
        self._name = name
        self._banner = banner
        self._description = description
        self._groups: Mapping[str, AnyGroup] = {}
        self._tasks: Mapping[str, AnyTask] = {}

    def __repr__(self):
        return f"<{self.__class__.__name__} name={self._name}>"

    @property
    def name(self):
        return self._name

    @property
    def banner(self) -> str:
        if self._banner is None:
            return ""
        return self._banner

    @property
    def description(self):
        return self._description if self._description is not None else self.name

    @property
    def subgroups(self) -> Mapping[str, AnyGroup]:
        names = list(self._groups.keys())
        names.sort()
        return {name: self._groups.get(name) for name in names}

    @property
    def subtasks(self) -> Mapping[str, AnyTask]:
        alias = list(self._tasks.keys())
        alias.sort()
        return {name: self._tasks.get(name) for name in alias}

    @property
    def contain_tasks(self) -> bool:
        if len(self.subtasks) > 0:
            return True
        for _, group in self.subgroups.items():
            if group.contain_tasks:
                return True
        return False

    def add_group(self, group: AnyGroup, alias: str | None = None) -> AnyGroup:
        alias = alias if alias is not None else group.name
        self._groups[alias] = group
        return group

    def add_task(self, task: AnyTask, alias: str | None = None) -> AnyTask:
        alias = alias if alias is not None else task.name
        self._tasks[alias] = task
        return task

    def get_task_by_alias(self, alias: str) -> AnyTask | None:
        return self._tasks.get(alias)

    def get_group_by_alias(self, alias: str) -> AnyGroup | None:
        return self._groups.get(alias)
