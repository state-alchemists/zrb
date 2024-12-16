from zrb.group.any_group import AnyGroup
from zrb.task.any_task import AnyTask


class Group(AnyGroup):
    def __init__(
        self, name: str, description: str | None = None, banner: str | None = None
    ):
        self._name = name
        self._banner = banner
        self._description = description
        self._groups: dict[str, AnyGroup] = {}
        self._tasks: dict[str, AnyTask] = {}

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
    def subgroups(self) -> dict[str, AnyGroup]:
        names = list(self._groups.keys())
        names.sort()
        return {name: self._groups.get(name) for name in names}

    @property
    def subtasks(self) -> dict[str, AnyTask]:
        alias = list(self._tasks.keys())
        alias.sort()
        return {name: self._tasks.get(name) for name in alias}

    def add_group(self, group: AnyGroup | str, alias: str | None = None) -> AnyGroup:
        real_group = Group(group) if isinstance(group, str) else group
        alias = alias if alias is not None else real_group.name
        self._groups[alias] = real_group
        return real_group

    def add_task(self, task: AnyTask, alias: str | None = None) -> AnyTask:
        alias = alias if alias is not None else task.name
        self._tasks[alias] = task
        return task

    def get_task_by_alias(self, alias: str) -> AnyTask | None:
        return self._tasks.get(alias)

    def get_group_by_alias(self, alias: str) -> AnyGroup | None:
        return self._groups.get(alias)
