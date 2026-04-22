from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.config.web_auth_config import WebAuthConfig
from zrb.group.any_group import AnyGroup
from zrb.runner.web_route.jinja_env import get_jinja_env
from zrb.runner.web_util.html import (
    get_html_auth_link,
    get_html_subgroup_info,
    get_html_subtask_info,
)
from zrb.runner.web_util.user import get_user_from_request

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

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/ui", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/ui/", response_class=HTMLResponse, include_in_schema=False)
    async def home_page_ui(request: Request) -> HTMLResponse:
        web_title = CFG.WEB_TITLE if CFG.WEB_TITLE.strip() != "" else root_group.name
        web_jargon = (
            CFG.WEB_JARGON if CFG.WEB_JARGON.strip() != "" else root_group.description
        )
        user = await get_user_from_request(web_auth_config, request)
        group_info = get_html_subgroup_info(user, "/ui/", root_group)
        task_info = get_html_subtask_info(user, "/ui/", root_group)
        auth_link = get_html_auth_link(user)
        html = (
            get_jinja_env()
            .get_template("home_page/view.html")
            .render(
                cfg=CFG,
                web_title=web_title,
                web_jargon=web_jargon,
                web_homepage_intro=CFG.WEB_HOMEPAGE_INTRO,
                group_info=group_info,
                task_info=task_info,
                auth_link=auth_link,
            )
        )
        return HTMLResponse(html)
