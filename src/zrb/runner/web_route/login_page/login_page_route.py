from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.config.web_auth_config import WebAuthConfig
from zrb.group.any_group import AnyGroup
from zrb.runner.web_route.jinja_env import get_jinja_env
from zrb.runner.web_util.branding import get_web_jargon, get_web_title

if TYPE_CHECKING:
    from fastapi import FastAPI


def serve_login_page(
    app: "FastAPI",
    root_group: AnyGroup,
    web_auth_config: WebAuthConfig,
) -> None:
    # lazy: heavy third-party
    from fastapi import Request
    from fastapi.responses import HTMLResponse

    @app.get("/login", response_class=HTMLResponse, include_in_schema=False)
    async def login(request: Request) -> HTMLResponse:
        web_title = get_web_title(root_group)
        web_jargon = get_web_jargon(root_group)
        html = (
            get_jinja_env()
            .get_template("login_page/view.html")
            .render(
                cfg=CFG,
                web_title=web_title,
                name=web_title,
                description=web_jargon,
            )
        )
        return HTMLResponse(html)
