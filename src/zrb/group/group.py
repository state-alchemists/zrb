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

    def remove_group(self, group: "AnyGroup | str"):
        original_groups_len = len(self._groups)
        if isinstance(group, AnyGroup):
            new_groups = {
                alias: existing_group
                for alias, existing_group in self._groups.items()
                if group != existing_group
            }
            if len(new_groups) == original_groups_len:
                raise ValueError(f"Cannot remove group {group} from {self}")
            self._groups = new_groups
            return
        # group is string, try to remove by alias
        new_groups = {
            alias: existing_group
            for alias, existing_group in self._groups.items()
            if alias != group
        }
        if len(new_groups) < original_groups_len:
            self._groups = new_groups
            return
        # if alias removal didn't work, try to remove by name
        new_groups = {
            alias: existing_group
            for alias, existing_group in self._groups.items()
            if existing_group.name != group
        }
        if len(new_groups) < original_groups_len:
            self._groups = new_groups
            return
        raise ValueError(f"Cannot remove group {group} from {self}")

    def remove_task(self, task: "AnyTask | str"):
        original_tasks_len = len(self._tasks)
        if isinstance(task, AnyTask):
            new_tasks = {
                alias: existing_task
                for alias, existing_task in self._tasks.items()
                if task != existing_task
            }
            if len(new_tasks) == original_tasks_len:
                raise ValueError(f"Cannot remove task {task} from {self}")
            self._tasks = new_tasks
            return
        # task is string, try to remove by alias
        new_tasks = {
            alias: existing_task
            for alias, existing_task in self._tasks.items()
            if alias != task
        }
        if len(new_tasks) < original_tasks_len:
            self._tasks = new_tasks
            return
        # if alias removal didn't work, try to remove by name
        new_tasks = {
            alias: existing_task
            for alias, existing_task in self._tasks.items()
            if existing_task.name != task
        }
        if len(new_tasks) < original_tasks_len:
            self._tasks = new_tasks
            return
        raise ValueError(f"Cannot remove task {task} from {self}")

    def get_task_by_alias(self, alias: str) -> AnyTask | None:
        return self._tasks.get(alias)

    def get_group_by_alias(self, alias: str) -> AnyGroup | None:
        return self._groups.get(alias)
