from collections.abc import Mapping
from .any_group import AnyGroup
from ..task import AnyTask


class Group(AnyGroup):

    def __init__(self, name: str, description: str | None = None):
        self._name = name
        self._description = description
        self._groups: Mapping[str, AnyGroup] = {}
        self._tasks: Mapping[str, AnyTask] = {}

    def __repr__(self):
        return f"<{self.__class__.__name__} name={self._name}>"

    def get_name(self):
        return self._name

    def get_description(self):
        return self._description if self._description is not None else self.get_name()

    def add_group(self, group: AnyGroup) -> AnyGroup:
        self._groups[group.get_name()] = group
        return group

    def add_task(self, task: AnyTask) -> AnyTask:
        self._tasks[task.get_name()] = task
        return task

    def get_sub_tasks(self) -> list[AnyTask]:
        names = list(self._tasks.keys())
        names.sort()
        return [self._tasks.get(name) for name in names]

    def get_task_by_name(self, name: str) -> AnyTask | None:
        return self._tasks.get(name)

    def get_sub_groups(self) -> list[AnyGroup]:
        names = list(self._groups.keys())
        names.sort()
        return [self._groups.get(name) for name in names]

    def get_group_by_name(self, name: str) -> AnyGroup | None:
        return self._groups.get(name)
