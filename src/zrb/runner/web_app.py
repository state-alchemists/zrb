import asyncio
import logging
import sys
from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.config.web_auth_config import WebAuthConfig
from zrb.group.any_group import AnyGroup
from zrb.runner.chat.chat_api_route import serve_chat_api
from zrb.runner.web_route.chat_page.chat_page_route import serve_chat_page
from zrb.runner.web_route.docs_route import serve_docs
from zrb.runner.web_route.error_page.serve_default_404 import serve_default_404
from zrb.runner.web_route.home_page.home_page_route import serve_home_page
from zrb.runner.web_route.login_api_route import serve_login_api
from zrb.runner.web_route.login_page.login_page_route import serve_login_page
from zrb.runner.web_route.logout_api_route import serve_logout_api
from zrb.runner.web_route.logout_page.logout_page_route import serve_logout_page
from zrb.runner.web_route.node_page.node_page_route import serve_node_page
from zrb.runner.web_route.refresh_token_api_route import serve_refresh_token_api
from zrb.runner.web_route.static.static_route import serve_static_resources
from zrb.runner.web_route.task_input_api_route import serve_task_input_api
from zrb.runner.web_route.task_session_api_route import serve_task_session_api
from zrb.session_state_logger.any_session_state_logger import AnySessionStateLogger

if TYPE_CHECKING:
    # We want fastapi to only be loaded when necessary to decrease footprint
    from fastapi import FastAPI

SHUTDOWN_TIMEOUT = 10


class CancelledErrorFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.exc_info and record.exc_info[0] is asyncio.CancelledError:
            return False
        msg = record.getMessage()
        if "Cancel" in msg and "running task" in msg:
            return False
        return True


def configure_uvicorn_logging() -> None:
    cancelled_filter = CancelledErrorFilter()
    for logger_name in [
        "uvicorn",
        "uvicorn.error",
        "uvicorn.protocols.http.httptools_impl",
        "uvicorn.protocols.http.h11_impl",
    ]:
        logger = logging.getLogger(logger_name)
        if not any(isinstance(f, CancelledErrorFilter) for f in logger.filters):
            logger.addFilter(cancelled_filter)


def create_web_app(
    root_group: AnyGroup,
    web_auth_config: WebAuthConfig,
    session_state_logger: AnySessionStateLogger,
) -> "FastAPI":
    from contextlib import asynccontextmanager

    from fastapi import FastAPI

    _COROS = []

    async def _cleanup_sessions():
        from zrb.runner.chat.chat_session_manager import ChatSessionManager

        # Skip aggressive cleanup in pytest mode
        if "pytest" in sys.modules:
            return
        session_mgr = ChatSessionManager.get_instance_sync()
        await session_mgr.cancel_all_sessions()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        capitalized_group_name = CFG.ROOT_GROUP_NAME.capitalize()
        for line in CFG.BANNER.split("\n") + [
            f"{capitalized_group_name} Server running on http://localhost:{CFG.WEB_HTTP_PORT}"
        ]:
            print(line, file=sys.stderr)

        yield

        # Cleanup on shutdown
        for coro in _COROS:
            coro.cancel()
        if _COROS:
            await asyncio.wait_for(
                asyncio.gather(*_COROS, return_exceptions=True),
                timeout=SHUTDOWN_TIMEOUT,
            )
        await _cleanup_sessions()

    app = FastAPI(
        title=CFG.WEB_TITLE,
        version=CFG.VERSION,
        summary="Your Automation Powerhouse",
        lifespan=lifespan,
        docs_url=None,
    )

    serve_default_404(app, root_group, web_auth_config)
    serve_static_resources(app, web_auth_config)
    serve_docs(app)
    serve_home_page(app, root_group, web_auth_config)
    serve_login_page(app, root_group, web_auth_config)
    serve_logout_page(app, root_group, web_auth_config)
    serve_chat_api(app, root_group, web_auth_config)
    serve_chat_page(app, root_group, web_auth_config)
    serve_node_page(app, root_group, web_auth_config)
    serve_login_api(app, web_auth_config)
    serve_logout_api(app, web_auth_config)
    serve_refresh_token_api(app, web_auth_config)
    serve_task_input_api(app, root_group, web_auth_config)
    serve_task_session_api(
        app, root_group, web_auth_config, session_state_logger, _COROS
    )
    return app
