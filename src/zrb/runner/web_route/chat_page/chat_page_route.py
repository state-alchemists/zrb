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
    from fastapi import FastAPI


def serve_chat_page(
    app: "FastAPI",
    root_group: AnyGroup,
    web_auth_config: WebAuthConfig,
) -> None:
    from fastapi import Request
    from fastapi.responses import HTMLResponse

    @app.get("/ui/chat", response_class=HTMLResponse)
    @app.get("/ui/chat/", response_class=HTMLResponse)
    async def chat_page(request: Request) -> HTMLResponse:
        _DIR = os.path.dirname(__file__)
        _GLOBAL_TEMPLATE = read_file(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "static",
                "global_template.html",
            )
        )
        _VIEW_TEMPLATE = read_file(os.path.join(_DIR, "view.html"))
        _CHAT_CSS = read_file(os.path.join(_DIR, "chat.css"))
        _CHAT_JS = read_file(os.path.join(_DIR, "chat.js"))

        web_title = f"{CFG.WEB_TITLE} - Chat"
        web_jargon = "Chat with your AI Assistant"
        user = await get_user_from_request(web_auth_config, request)
        auth_link = get_html_auth_link(user)

        content = fstring_format(
            _VIEW_TEMPLATE,
            {
                "web_title": web_title,
                "web_jargon": web_jargon,
                "auth_link": auth_link,
            },
        )

        return HTMLResponse(
            fstring_format(
                _GLOBAL_TEMPLATE,
                {
                    "CFG": CFG,
                    "root_group": root_group,
                    "content": f"""
<style>
{_CHAT_CSS}
</style>
{content}
<script>
{_CHAT_JS}
</script>
                    """,
                },
            )
        )
