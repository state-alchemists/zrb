import os
from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.config.web_auth_config import WebAuthConfig
from zrb.group.any_group import AnyGroup
from zrb.runner.web_util.html import (
    get_html_auth_link,
    get_html_subgroup_info,
    get_html_subtask_info,
)
from zrb.runner.web_util.user import get_user_from_request
from zrb.util.file import read_file
from zrb.util.string.format import fstring_format

if TYPE_CHECKING:
    # We want fastapi to only be loaded when necessary to decrease footprint
    from fastapi import FastAPI


def serve_home_page(
    app: "FastAPI",
    root_group: AnyGroup,
    web_auth_config: WebAuthConfig,
) -> None:
    from fastapi import Request
    from fastapi.responses import HTMLResponse

    # Serve homepage
    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/ui", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/ui/", response_class=HTMLResponse, include_in_schema=False)
    async def home_page_ui(request: Request) -> HTMLResponse:
        _DIR = os.path.dirname(__file__)
        _GLOBAL_TEMPLATE = read_file(
            os.path.join(os.path.dirname(_DIR), "static", "global_template.html")
        )
        _VIEW_TEMPLATE = read_file(os.path.join(_DIR, "view.html"))
        web_title = CFG.WEB_TITLE if CFG.WEB_TITLE.strip() != "" else root_group.name
        web_jargon = (
            CFG.WEB_JARGON if CFG.WEB_JARGON.strip() != "" else root_group.description
        )
        user = await get_user_from_request(web_auth_config, request)
        group_info = get_html_subgroup_info(user, "/ui/", root_group)
        task_info = get_html_subtask_info(user, "/ui/", root_group)
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
                            "web_homepage_intro": CFG.WEB_HOMEPAGE_INTRO,
                            "group_info": group_info,
                            "task_info": task_info,
                            "name": root_group.name,
                            "description": root_group.description,
                            "auth_link": auth_link,
                        },
                    ),
                },
            )
        )
