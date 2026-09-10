import secrets

from pydantic import BaseModel, ConfigDict

from zrb.group.any_group import AnyGroup
from zrb.task.any_task import AnyTask


class User(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    username: str
    password: str = ""
    is_super_admin: bool = False
    is_guest: bool = False
    accessible_tasks: list[AnyTask | str] = []

    def is_password_match(self, password: str) -> bool:
        """Check a plaintext password against this user's, in constant time."""
        # Constant-time compare to avoid a timing side-channel on the password.
        # Encode to bytes so non-ASCII passwords compare safely (secrets.compare_digest
        # rejects non-ASCII str). Passwords are still configured in plaintext by the
        # host app — hashing them at rest would change that public config contract.
        return secrets.compare_digest(self.password.encode(), password.encode())

    def can_access_group(self, group: AnyGroup) -> bool:
        """Whether this user may see `group`.

        True for a super admin, or when the user can access at least one task
        within the group or its subgroups.
        """
        if self.is_super_admin:
            return True
        all_tasks = group.get_all_subtasks(web_only=True)
        if any(self.can_access_task(task) for task in all_tasks):
            return True
        return False

    def can_access_task(self, task: AnyTask) -> bool:
        """Whether this user may run `task`.

        True for a super admin, or when the task appears in
        `accessible_tasks` by name or by identity.
        """
        if self.is_super_admin:
            return True
        if task.name in self.accessible_tasks or task in self.accessible_tasks:
            return True
        return False
