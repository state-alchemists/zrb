import os

from fastapi.responses import HTMLResponse

from zrb.group.any_group import AnyGroup
from zrb.runner.web_config import User
from zrb.runner.web_util import get_html_subgroup_info, get_html_subtask_info
from zrb.util.file import read_file
from zrb.util.string.format import fstring_format

_DIR = os.path.dirname(__file__)
_VIEW_TEMPLATE = read_file(os.path.join(_DIR, "view.html"))


def show_home_page(user: User, root_group: AnyGroup):
    group_info = get_html_subgroup_info(user, "ui/", root_group)
    task_info = get_html_subtask_info(user, "ui/", root_group)
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
