import os

from zrb.group.any_group import AnyGroup
from zrb.util.file import read_file
from zrb.util.group import get_non_empty_subgroups, get_subtasks
from zrb.util.string.format import fstring_format

_DIR = os.path.dirname(__file__)

_VIEW_TEMPLATE = read_file(os.path.join(_DIR, "view.html"))
_GROUP_INFO_TEMPLATE = read_file(os.path.join(_DIR, "partial", "group_info.html"))
_GROUP_LI_TEMPLATE = read_file(os.path.join(_DIR, "partial", "group_li.html"))
_TASK_INFO_TEMPLATE = read_file(os.path.join(_DIR, "partial", "task_info.html"))
_TASK_LI_TEMPLATE = read_file(os.path.join(_DIR, "partial", "task_li.html"))


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
