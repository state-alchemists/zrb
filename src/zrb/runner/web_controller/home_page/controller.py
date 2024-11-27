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


def handle_home_page(root_group: AnyGroup):
    from fastapi.responses import HTMLResponse

    subgroups = get_non_empty_subgroups(root_group, web_only=True)
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
                            {"caption": name, "description": group.description},
                        )
                        for name, group in subgroups.items()
                    ]
                )
            },
        )
    )
    subtasks = get_subtasks(root_group, web_only=True)
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
                            {"caption": name, "description": task.description},
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
                "name": root_group.name,
                "description": root_group.description,
            },
        )
    )
