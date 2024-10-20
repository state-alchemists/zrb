from collections.abc import Mapping
from .any_group import AnyGroup
from ..task import AnyTask


class Group(AnyGroup):

    def __init__(
        self, name: str, banner: str | None = None, description: str | None = None
    ):
        self._name = name
        self._banner = banner
        self._description = description
        self._groups: Mapping[str, AnyGroup] = {}
        self._tasks: Mapping[str, AnyTask] = {}

    def __repr__(self):
        return f"<{self.__class__.__name__} name={self._name}>"

    def get_name(self):
        return self._name

    def get_banner(self) -> str:
        if self._banner is None:
            return ""
        return self._banner

    def get_description(self):
        return self._description if self._description is not None else self.get_name()

    def add_group(self, group: AnyGroup) -> AnyGroup:
        self._groups[group.get_name()] = group
        return group

    def add_task(self, task: AnyTask, alias: str | None = None) -> AnyTask:
        alias = alias if alias is not None else task.get_name()
        self._tasks[alias] = task
        return task

    def get_sub_tasks(self) -> Mapping[str, AnyTask]:
        alias = list(self._tasks.keys())
        alias.sort()
        return {name: self._tasks.get(name) for name in alias}

    def get_task_by_alias(self, alias: str) -> AnyTask | None:
        return self._tasks.get(alias)

    def get_sub_groups(self) -> Mapping[str, AnyGroup]:
        names = list(self._groups.keys())
        names.sort()
        return {name: self._groups.get(name) for name in names}

    def get_group_by_name(self, name: str) -> AnyGroup | None:
        return self._groups.get(name)
