from typing import TYPE_CHECKING

from zrb.group.any_group import AnyGroup
from zrb.runner.web_config.config import WebConfig
from zrb.runner.web_route.error_page.show_error_page import show_error_page
from zrb.runner.web_util.user import get_user_from_request

if TYPE_CHECKING:
    # We want fastapi to only be loaded when necessary to decrease footprint
    from fastapi import FastAPI


def serve_default_404(
    app: "FastAPI",
    root_group: AnyGroup,
    web_config: WebConfig,
) -> None:
    from fastapi import Request
    from fastapi.exception_handlers import http_exception_handler
    from fastapi.responses import HTMLResponse

    @app.exception_handler(404)
    async def default_404(request: Request, exc: Exception) -> HTMLResponse:
        if request.url.path.startswith("/api"):
            # Re-raise the exception to let FastAPI handle it
            return await http_exception_handler(request, exc)
        user = await get_user_from_request(web_config, request)
        return show_error_page(user, root_group, 404, "Not found")
