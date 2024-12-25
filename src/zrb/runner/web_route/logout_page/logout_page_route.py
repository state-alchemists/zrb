import os
from typing import TYPE_CHECKING

from zrb.group.any_group import AnyGroup
from zrb.runner.web_config.config import WebConfig
from zrb.runner.web_util.html import get_html_auth_link
from zrb.runner.web_util.user import get_user_from_request
from zrb.util.file import read_file
from zrb.util.string.format import fstring_format

if TYPE_CHECKING:
    # We want fastapi to only be loaded when necessary to decrease footprint
    from fastapi import FastAPI


def serve_logout_page(
    app: "FastAPI",
    root_group: AnyGroup,
    web_config: WebConfig,
) -> None:
    from fastapi import Request
    from fastapi.responses import HTMLResponse

    @app.get("/logout", response_class=HTMLResponse, include_in_schema=False)
    async def logout(request: Request) -> HTMLResponse:
        _DIR = os.path.dirname(__file__)
        _VIEW_TEMPLATE = read_file(os.path.join(_DIR, "view.html"))
        user = await get_user_from_request(web_config, request)
        auth_link = get_html_auth_link(user)
        return HTMLResponse(
            fstring_format(
                _VIEW_TEMPLATE,
                {
                    "name": root_group.name,
                    "description": root_group.description,
                    "auth_link": auth_link,
                    "user": user,
                },
            )
        )
