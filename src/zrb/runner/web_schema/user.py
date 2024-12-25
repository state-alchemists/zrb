from pydantic import BaseModel, ConfigDict

from zrb.group.any_group import AnyGroup
from zrb.task.any_task import AnyTask
from zrb.util.group import get_all_subtasks


class User(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    username: str
    password: str = ""
    is_super_admin: bool = False
    is_guest: bool = False
    accessible_tasks: list[AnyTask | str] = []

    def is_password_match(self, password: str) -> bool:
        return self.password == password

    def can_access_group(self, group: AnyGroup) -> bool:
        if self.is_super_admin:
            return True
        all_tasks = get_all_subtasks(group, web_only=True)
        if any(self.can_access_task(task) for task in all_tasks):
            return True
        return False

    def can_access_task(self, task: AnyTask) -> bool:
        if self.is_super_admin:
            return True
        if task.name in self.accessible_tasks or task in self.accessible_tasks:
            return True
        return False
