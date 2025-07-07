import os
from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.config.web_auth_config import WebAuthConfig
from zrb.group.any_group import AnyGroup
from zrb.runner.web_util.html import get_html_auth_link
from zrb.runner.web_util.user import get_user_from_request
from zrb.util.file import read_file
from zrb.util.string.format import fstring_format

if TYPE_CHECKING:
    # We want fastapi to only be loaded when necessary to decrease footprint
    from fastapi import FastAPI


def serve_login_page(
    app: "FastAPI",
    root_group: AnyGroup,
    web_auth_config: WebAuthConfig,
) -> None:
    from fastapi import Request
    from fastapi.responses import HTMLResponse

    @app.get("/login", response_class=HTMLResponse, include_in_schema=False)
    async def login(request: Request) -> HTMLResponse:
        _DIR = os.path.dirname(__file__)
        _GLOBAL_TEMPLATE = read_file(
            os.path.join(os.path.dirname(_DIR), "static", "global_template.html")
        )
        _VIEW_TEMPLATE = read_file(os.path.join(_DIR, "view.html"))
        user = await get_user_from_request(web_auth_config, request)
        web_title = CFG.WEB_TITLE if CFG.WEB_TITLE.strip() != "" else root_group.name
        web_jargon = (
            CFG.WEB_JARGON if CFG.WEB_JARGON.strip() != "" else root_group.description
        )
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
                            "name": web_title,
                            "description": web_jargon,
                            "auth_link": auth_link,
                        },
                    ),
                },
            )
        )
