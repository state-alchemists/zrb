import os

from zrb.group.any_group import AnyGroup
from zrb.util.group import get_non_empty_subgroups, get_subtasks
from zrb.util.string.format import fstring_format

_DIR = os.path.dirname(__file__)

with open(os.path.join(_DIR, "view.html"), "r") as f:
    _VIEW_TEMPLATE = f.read()

with open(os.path.join(_DIR, "partial", "group_info.html")) as f:
    _GROUP_INFO_TEMPLATE = f.read()

with open(os.path.join(_DIR, "partial", "group_li.html")) as f:
    _GROUP_LI_TEMPLATE = f.read()

with open(os.path.join(_DIR, "partial", "task_info.html")) as f:
    _TASK_INFO_TEMPLATE = f.read()

with open(os.path.join(_DIR, "partial", "task_li.html")) as f:
    _TASK_LI_TEMPLATE = f.read()


def handle_group_info_ui(root_group: AnyGroup, group: AnyGroup, url: str):
    from fastapi.responses import HTMLResponse

    url_parts = url.split("/")
    parent_url_parts = url_parts[:-2] + [""]
    parent_url = "/".join(parent_url_parts)
    subgroups = get_non_empty_subgroups(group, web_only=True)
    group_info = (
        ""
        if len(subgroups) == 0
        else fstring_format(
            _GROUP_INFO_TEMPLATE,
            {
                "group_li": "\n".join(
                    [
                        fstring_format(
                            _GROUP_LI_TEMPLATE,
                            {
                                "caption": name,
                                "url": url,
                                "description": group.description,
                            },
                        )
                        for name, group in subgroups.items()
                    ]
                )
            },
        )
    )
    subtasks = get_subtasks(group, web_only=True)
    task_info = (
        ""
        if len(subtasks) == 0
        else fstring_format(
            _TASK_INFO_TEMPLATE,
            {
                "task_li": "\n".join(
                    [
                        fstring_format(
                            _TASK_LI_TEMPLATE,
                            {
                                "caption": name,
                                "url": url,
                                "description": task.description,
                            },
                        )
                        for name, task in subtasks.items()
                    ]
                )
            },
        )
    )
    return HTMLResponse(
        fstring_format(
            _VIEW_TEMPLATE,
            {
                "group_info": group_info,
                "task_info": task_info,
                "name": group.name,
                "description": group.description,
                "root_name": root_group.name,
                "root_description": root_group.description,
                "url": url,
                "parent_url": parent_url,
            },
        )
    )
