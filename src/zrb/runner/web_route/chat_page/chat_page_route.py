from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.config.web_auth_config import WebAuthConfig
from zrb.group.any_group import AnyGroup
from zrb.runner.web_route.jinja_env import get_jinja_env
from zrb.runner.web_util.html import get_html_auth_link
from zrb.runner.web_util.user import get_user_from_request

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
        web_title = f"{CFG.WEB_TITLE} - Chat"
        web_jargon = "Chat with your AI Assistant"
        user = await get_user_from_request(web_auth_config, request)
        auth_link = get_html_auth_link(user)
        html = (
            get_jinja_env()
            .get_template("chat_page/view.html")
            .render(
                cfg=CFG,
                web_title=web_title,
                web_jargon=web_jargon,
                auth_link=auth_link,
            )
        )
        return HTMLResponse(html)
