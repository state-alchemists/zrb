import os

from zrb.group.any_group import AnyGroup
from zrb.runner.web_config import User
from zrb.runner.web_util import (
    get_html_auth_link,
    get_html_subgroup_info,
    get_html_subtask_info,
)
from zrb.util.file import read_file
from zrb.util.string.format import fstring_format


def show_home_page(user: User, root_group: AnyGroup):
    from fastapi.responses import HTMLResponse

    _DIR = os.path.dirname(__file__)
    _VIEW_TEMPLATE = read_file(os.path.join(_DIR, "view.html"))
    group_info = get_html_subgroup_info(user, "/ui/", root_group)
    task_info = get_html_subtask_info(user, "/ui/", root_group)
    auth_link = get_html_auth_link(user)
    return HTMLResponse(
        fstring_format(
            _VIEW_TEMPLATE,
            {
                "group_info": group_info,
                "task_info": task_info,
                "name": root_group.name,
                "description": root_group.description,
                "auth_link": auth_link,
            },
        )
    )
