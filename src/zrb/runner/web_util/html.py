from html import escape

from zrb.group.any_group import AnyGroup
from zrb.runner.web_schema.user import User
from zrb.task.any_task import AnyTask

# Every builder here returns markup that the page templates insert with
# `| safe`, so each interpolated value is escaped on the way in: names,
# descriptions and usernames come from user code or a login form, not from us.


def get_html_auth_link(user: User) -> str:
    username = escape(user.username)
    if user.is_guest and user.is_super_admin:
        return f"Hi, {username}"
    if user.is_guest:
        return f'Hi, {username} <a href="/login">Login 🔑</a>'
    return f'Hi, {username} <a href="/logout">Logout 🚪</a>'


def get_html_subtask_info(user: User, parent_url: str, parent_group: AnyGroup) -> str:
    subtasks = parent_group.get_subtasks(web_only=True)
    task_li = "\n".join(
        [
            get_html_task_li(parent_url, alias, subtask)
            for alias, subtask in subtasks.items()
            if user.can_access_task(subtask)
        ]
    )
    if task_li.strip() == "":
        return ""
    return f"<h5>Tasks</h5><ul>{task_li}</ul>"


def get_html_task_li(parent_url: str, alias: str, task: AnyTask) -> str:
    if not parent_url.endswith("/"):
        parent_url += "/"
    href = escape(f"{parent_url}{alias}")
    return f'<li><a href="{href}">{escape(alias)}</a> {escape(task.description)}</li>'


def get_html_subgroup_info(user: User, parent_url: str, parent_group: AnyGroup) -> str:
    subgroups = parent_group.get_non_empty_subgroups(web_only=True)
    group_li = "\n".join(
        [
            get_html_group_li(parent_url, alias, subgroup)
            for alias, subgroup in subgroups.items()
            if user.can_access_group(subgroup)
        ]
    )
    if group_li.strip() == "":
        return ""
    return f"<h5>Groups</h5><ul>{group_li}</ul>"


def get_html_group_li(parent_url: str, alias: str, group: AnyGroup) -> str:
    if not parent_url.endswith("/"):
        parent_url += "/"
    href = escape(f"{parent_url}{alias}")
    return f'<li><a href="{href}">{escape(alias)}</a> {escape(group.description)}</li>'
