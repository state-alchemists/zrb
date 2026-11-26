import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.config.web_auth_config import WebAuthConfig
from zrb.group.any_group import AnyGroup
from zrb.runner.chat.chat_api_route import serve_chat_api
from zrb.runner.chat.chat_session_manager import ChatSessionManager
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
    from fastapi import FastAPI


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


def should_skip_session_cleanup() -> bool:
    """Whether the chat sessions are left to whoever drives the app.

    True under pytest: the suite builds the app in-process and owns
    `ChatSessionManager`, so a test run must not cancel the sessions it holds.
    """
    return "pytest" in sys.modules


async def cancel_task_runs(
    task_runs: "list[asyncio.Task]", timeout_seconds: float
) -> None:
    """Cancel *task_runs*, waiting at most *timeout_seconds* for them to stop.

    ``asyncio.wait``, not ``asyncio.wait_for(gather(...))``: a gather future is
    only done once every child is, so on timeout `wait_for` waits for the
    cancellation it just requested — and a run that catches `CancelledError`
    again holds the shutdown there for as long as it likes, which is the one
    thing the timeout exists to prevent. Shutdown still has the chat sessions to
    cancel after this, so a survivor is named and left behind.
    """
    if not task_runs:
        return
    for task_run in task_runs:
        task_run.cancel()
    done, pending = await asyncio.wait(set(task_runs), timeout=timeout_seconds)
    for task_run in done:
        _consume_outcome(task_run)
    if not pending:
        return
    for task_run in pending:
        # Nothing awaits a survivor any more; consume whatever it ends with so
        # asyncio does not report it as never retrieved.
        task_run.add_done_callback(_consume_outcome)
    names = ", ".join(sorted(task_run.get_name() for task_run in pending))
    CFG.LOGGER.warning(
        f"Web shutdown waited {timeout_seconds}s for {len(task_runs)} task "
        f"run(s); {len(pending)} still running ({names}). Continuing with chat "
        "session cleanup."
    )


def _consume_outcome(task_run: "asyncio.Task") -> None:
    """Read a finished run's result or exception so asyncio stops holding it."""
    if not task_run.cancelled():
        task_run.exception()


def create_web_app(
    root_group: AnyGroup,
    web_auth_config: WebAuthConfig,
    session_state_logger: AnySessionStateLogger,
) -> "FastAPI":
    # lazy: heavy third-party
    from fastapi import FastAPI

    _COROS = []

    async def _cleanup_sessions():
        if should_skip_session_cleanup():
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

        await cancel_task_runs(_COROS, CFG.WEB_SHUTDOWN_TIMEOUT / 1000)
        await _cleanup_sessions()

    app = FastAPI(
        title=CFG.WEB_TITLE,
        version=CFG.VERSION,
        summary="A coding agent with a built-in task DAG",
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
