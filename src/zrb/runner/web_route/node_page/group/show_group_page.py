import os

from zrb.config.config import CFG
from zrb.group.any_group import AnyGroup
from zrb.runner.web_schema.user import User
from zrb.runner.web_util.html import (
    get_html_auth_link,
    get_html_subgroup_info,
    get_html_subtask_info,
)
from zrb.util.file import read_file
from zrb.util.string.format import fstring_format


def show_group_page(user: User, root_group: AnyGroup, group: AnyGroup, url: str):
    from fastapi.responses import HTMLResponse

    _DIR = os.path.dirname(__file__)
    _GLOBAL_TEMPLATE = read_file(
        os.path.join(
            os.path.dirname(os.path.dirname(_DIR)), "static", "global_template.html"
        )
    )
    _VIEW_TEMPLATE = read_file(os.path.join(_DIR, "view.html"))
    web_title = CFG.WEB_TITLE if CFG.WEB_TITLE.strip() != "" else root_group.name
    web_jargon = (
        CFG.WEB_JARGON if CFG.WEB_JARGON.strip() != "" else root_group.description
    )
    url_parts = url.split("/")
    parent_url_parts = url_parts[:-2] + [""]
    parent_url = "/".join(parent_url_parts)
    group_info = get_html_subgroup_info(user, url, group)
    task_info = get_html_subtask_info(user, url, group)
    auth_link = get_html_auth_link(user)
    return HTMLResponse(
        fstring_format(
            _GLOBAL_TEMPLATE,
            {
                "CFG": CFG,
                "root_group": root_group,
                "content": fstring_format(
                    _VIEW_TEMPLATE,
                    {
                        "web_title": web_title,
                        "web_jargon": web_jargon,
                        "group_info": group_info,
                        "task_info": task_info,
                        "name": group.name,
                        "description": group.description,
                        "auth_link": auth_link,
                        "url": url,
                        "parent_url": parent_url,
                    },
                ),
            },
        )
    )
