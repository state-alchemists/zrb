import os
import re
from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.config.web_auth_config import WebAuthConfig
from zrb.runner.web_util.user import get_user_from_request
from zrb.util.file import read_file
from zrb.util.string.format import fstring_format

if TYPE_CHECKING:
    from fastapi import FastAPI, Request


_DIR = os.path.dirname(__file__)


def _get_templates():
    _GLOBAL_TEMPLATE = read_file(
        os.path.join(os.path.dirname(_DIR), "static", "global_template.html")
    )
    _CHAT_TEMPLATE = read_file(os.path.join(_DIR, "chat.html"))
    return _GLOBAL_TEMPLATE, _CHAT_TEMPLATE


async def get_chat_page_html(user) -> "HTMLResponse":
    from fastapi.responses import HTMLResponse

    _GLOBAL_TEMPLATE, _CHAT_TEMPLATE = _get_templates()
    temp_template = _GLOBAL_TEMPLATE.replace("{content}", "__CHAT_CONTENT__")
    processed_template = fstring_format(temp_template, {"CFG": CFG, "root_group": None})
    chat_content = _CHAT_TEMPLATE.replace("{{", "{").replace("}}", "}")
    result = processed_template.replace("__CHAT_CONTENT__", chat_content)
    return HTMLResponse(result)


def serve_chat_page(
    app: "FastAPI",
    web_auth_config: WebAuthConfig,
) -> None:
    from fastapi import Request
    from fastapi.responses import HTMLResponse

    async def chat_page_ui(request: Request) -> HTMLResponse:
        user = await get_user_from_request(web_auth_config, request)
        return await get_chat_page_html(user)

    app.add_api_route(
        "/chat",
        chat_page_ui,
        response_class=HTMLResponse,
        include_in_schema=False,
        methods=["GET"],
    )
    app.add_api_route(
        "/chat/",
        chat_page_ui,
        response_class=HTMLResponse,
        include_in_schema=False,
        methods=["GET"],
    )
