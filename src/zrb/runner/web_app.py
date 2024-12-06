import asyncio
import os
import sys
from datetime import datetime, timedelta
from typing import Any

from zrb.config import BANNER, WEB_HTTP_PORT
from zrb.context.shared_context import SharedContext
from zrb.group.any_group import AnyGroup
from zrb.runner.web_controller.group_info_ui.controller import handle_group_info_ui
from zrb.runner.web_controller.home_page.controller import handle_home_page
from zrb.runner.web_controller.task_ui.controller import handle_task_ui
from zrb.runner.web_util import NewSessionResponse
from zrb.session.session import Session
from zrb.session_state_log.session_state_log import SessionStateLog, SessionStateLogList
from zrb.session_state_logger.default_session_state_logger import (
    default_session_state_logger,
)
from zrb.task.any_task import AnyTask
from zrb.util.group import extract_node_from_args, get_node_path


def create_app(root_group: AnyGroup, port: int = WEB_HTTP_PORT):
    from contextlib import asynccontextmanager

    from fastapi import FastAPI, HTTPException, Query, Request
    from fastapi.responses import FileResponse, HTMLResponse
    from fastapi.staticfiles import StaticFiles

    _STATIC_DIR = os.path.join(os.path.dirname(__file__), "web_controller", "static")
    _COROS = []

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        for line in BANNER.split("\n") + [
            f"Zrb Server running on http://localhost:{port}"
        ]:
            print(line, file=sys.stderr)
        yield
        for coro in _COROS:
            coro.cancel()
        asyncio.gather(*_COROS)

    app = FastAPI(title="zrb", lifespan=lifespan)

    # Serve static files
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/ui", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/ui/", response_class=HTMLResponse, include_in_schema=False)
    async def home_page():
        return handle_home_page(root_group)

    @app.get("/static/{file_path:path}", include_in_schema=False)
    async def static_files(file_path: str):
        full_path = os.path.join(_STATIC_DIR, file_path)
        if os.path.isfile(full_path):
            return FileResponse(full_path)
        raise HTTPException(status_code=404, detail="File not found")

    @app.get("/ui/{path:path}", include_in_schema=False)
    async def ui_page(path: str):
        # Avoid capturing '/ui' itself
        if not path:
            raise HTTPException(status_code=404, detail="Not Found")
        args = path.strip("/").split("/")
        node, node_path, residual_args = extract_node_from_args(root_group, args)
        url = f"/ui/{'/'.join(node_path)}/"
        if isinstance(node, AnyTask):
            shared_ctx = SharedContext(env=dict(os.environ))
            session = Session(shared_ctx=shared_ctx, root_group=root_group)
            return handle_task_ui(root_group, node, session, url, residual_args)
        elif isinstance(node, AnyGroup):
            return handle_group_info_ui(root_group, node, url)
        raise HTTPException(status_code=404, detail="Not Found")

    @app.post("/api/{path:path}")
    async def create_new_session(
        path: str, request: Request = None
    ) -> NewSessionResponse:
        """
        Creating new session
        """
        args = path.strip("/").split("/")
        node, _, residual_args = extract_node_from_args(root_group, args)
        if isinstance(node, AnyTask):
            session_name = residual_args[0] if residual_args else None
            if not session_name:
                body = await request.json()
                shared_ctx = SharedContext(env=dict(os.environ))
                session = Session(shared_ctx=shared_ctx, root_group=root_group)
                coro = asyncio.create_task(node.async_run(session, str_kwargs=body))
                _COROS.append(coro)
                coro.add_done_callback(lambda coro: _COROS.remove(coro))
                return NewSessionResponse(session_name=session.name)
        raise HTTPException(status_code=404, detail="Not Found")

    @app.get("/api/{path:path}", response_model=SessionStateLog | SessionStateLogList)
    async def get_session(
        path: str,
        min_start_query: str = Query(default=None, alias="from"),
        max_start_query: str = Query(default=None, alias="to"),
        page: int = Query(default=0, alias="page"),
        limit: int = Query(default=10, alias="limit"),
    ):
        """
        Getting existing session or sessions
        """
        args = path.strip("/").split("/")
        node, _, residual_args = extract_node_from_args(root_group, args)
        if isinstance(node, AnyTask) and residual_args:
            if residual_args[0] == "list":
                task_path = get_node_path(root_group, node)
                max_start_time = (
                    datetime.now()
                    if max_start_query is None
                    else datetime.strptime(max_start_query, "%Y-%m-%d %H:%M:%S")
                )
                min_start_time = (
                    max_start_time - timedelta(hours=1)
                    if min_start_query is None
                    else datetime.strptime(min_start_query, "%Y-%m-%d %H:%M:%S")
                )
                return list_sessions(
                    task_path, min_start_time, max_start_time, page, limit
                )
            else:
                return read_session(residual_args[0])
        raise HTTPException(status_code=404, detail="Not Found")

    def list_sessions(
        task_path: list[str],
        min_start_time: datetime,
        max_start_time: datetime,
        page: int,
        limit: int,
    ) -> SessionStateLogList:
        try:
            return default_session_state_logger.list(
                task_path,
                min_start_time=min_start_time,
                max_start_time=max_start_time,
                page=page,
                limit=limit,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    def read_session(session_name: str) -> SessionStateLog:
        try:
            return default_session_state_logger.read(session_name)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app
