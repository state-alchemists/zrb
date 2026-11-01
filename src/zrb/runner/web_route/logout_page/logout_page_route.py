from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.config.web_auth_config import WebAuthConfig
from zrb.group.any_group import AnyGroup
from zrb.runner.web_route.jinja_env import get_jinja_env
from zrb.runner.web_util.branding import get_web_jargon, get_web_title
from zrb.runner.web_util.user import get_user_from_request

if TYPE_CHECKING:
    from fastapi import FastAPI


def serve_logout_page(
    app: "FastAPI",
    root_group: AnyGroup,
    web_auth_config: WebAuthConfig,
) -> None:
    # lazy: heavy third-party
    from fastapi import Request
    from fastapi.responses import HTMLResponse

    @app.get("/logout", response_class=HTMLResponse, include_in_schema=False)
    async def logout(request: Request) -> HTMLResponse:
        user = await get_user_from_request(web_auth_config, request)
        web_title = get_web_title(root_group)
        web_jargon = get_web_jargon(root_group)
        html = (
            get_jinja_env()
            .get_template("logout_page/view.html")
            .render(
                cfg=CFG,
                web_title=web_title,
                name=web_title,
                description=web_jargon,
                username=user.username,
            )
        )
        return HTMLResponse(html)
