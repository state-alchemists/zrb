from pydantic import BaseModel

from zrb.group.any_group import AnyGroup
from zrb.runner.web_config import User
from zrb.task.any_task import AnyTask
from zrb.util.group import get_non_empty_subgroups, get_subtasks


class NewSessionResponse(BaseModel):
    session_name: str


def url_to_args(url: str) -> list[str]:
    stripped_url = url.strip("/")
    return [part for part in stripped_url.split("/") if part.strip() != ""]


def node_path_to_url(args: list[str]) -> str:
    pruned_args = [part for part in args if part.strip() != ""]
    stripped_url = "/".join(pruned_args)
    return f"/{stripped_url}/"


def get_html_subtask_info(user: User, parent_url: str, parent_group: AnyGroup) -> str:
    subtasks = get_subtasks(parent_group, web_only=True)
    task_li = "\n".join(
        [
            get_html_task_li(parent_url, alias, subtask)
            for alias, subtask in subtasks.items()
            if user.can_access_task(subtask)
        ]
    )
    if task_li.strip() == "":
        return ""
    return f"<h5>Groups</h5><ul>{task_li}</ul>"


def get_html_task_li(parent_url: str, alias: str, task: AnyTask) -> str:
    if not parent_url.endswith("/"):
        parent_url += "/"
    return f'<li><a href="{parent_url}{alias}">{alias}</a> {task.description}</li>'


def get_html_subgroup_info(user: User, parent_url: str, parent_group: AnyGroup) -> str:
    subgroups = get_non_empty_subgroups(parent_group, web_only=True)
    group_li = "\n".join(
        [
            get_html_group_li(parent_url, alias, subgroup)
            for alias, subgroup in subgroups.items()
            if user.can_access_group(subgroup)
        ]
    )
    if group_li.strip() == "":
        return ""
    return f"<h5>Tasks</h5><ul>{group_li}</ul>"


def get_html_group_li(parent_url: str, alias: str, group: AnyGroup) -> str:
    if not parent_url.endswith("/"):
        parent_url += "/"
    return f'<li><a href="{parent_url}{alias}">{alias}</a> {group.description}</li>'
