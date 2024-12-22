import os

from zrb.group.any_group import AnyGroup
from zrb.runner.web_config import User
from zrb.runner.web_util import get_html_subgroup_info, get_html_subtask_info
from zrb.util.file import read_file
from zrb.util.string.format import fstring_format


def show_group_info_page(user: User, root_group: AnyGroup, group: AnyGroup, url: str):
    from fastapi.responses import HTMLResponse

    _DIR = os.path.dirname(__file__)
    _VIEW_TEMPLATE = read_file(os.path.join(_DIR, "view.html"))
    url_parts = url.split("/")
    parent_url_parts = url_parts[:-2] + [""]
    parent_url = "/".join(parent_url_parts)
    group_info = get_html_subgroup_info(user, parent_url, root_group)
    task_info = get_html_subtask_info(user, parent_url, root_group)
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
