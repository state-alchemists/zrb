import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from uvicorn import Config, Server

from zrb.config import BANNER, WEB_HTTP_PORT
from zrb.context.any_context import AnyContext
from zrb.context.shared_context import SharedContext
from zrb.group.any_group import AnyGroup
from zrb.runner.web_app.group_info_ui.controller import handle_group_info_ui
from zrb.runner.web_app.home_page.controller import handle_home_page
from zrb.runner.web_app.task_ui.controller import handle_task_ui
from zrb.session.session import Session
from zrb.session_state_log.session_state_log import SessionStateLog, SessionStateLogList
from zrb.session_state_logger.default_session_state_logger import (
    default_session_state_logger,
)
from zrb.task.any_task import AnyTask
from zrb.util.group import extract_node_from_args, get_node_path


async def run_web_server(
    web_server_ctx: AnyContext, root_group: AnyGroup, port: int = WEB_HTTP_PORT
):

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Print the banner on startup
        for line in BANNER.split("\n") + [
            f"Zrb Server running on http://localhost:{WEB_HTTP_PORT}"
        ]:
            web_server_ctx.print(line)
        yield

    app = FastAPI(title="zrb", lifespan=lifespan)
    _STATIC_DIR = os.path.join(os.path.dirname(__file__), "web_app", "static")

    # Serve static files
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    @app.get("/", response_class=HTMLResponse)
    @app.get("/ui", response_class=HTMLResponse)
    async def home_page():
        return handle_home_page(root_group)

    @app.get("/static/{file_path:path}")
    async def static_files(file_path: str):
        full_path = os.path.join(_STATIC_DIR, file_path)
        if os.path.isfile(full_path):
            return FileResponse(full_path)
        raise HTTPException(status_code=404, detail="File not found")

    @app.get("/ui/{path:path}")
    async def ui_page(path: str):
        args = path.split("/")
        node, node_path, residual_args = extract_node_from_args(root_group, args)
        url = f"/ui/{'/'.join(node_path)}/"
        if isinstance(node, AnyTask):
            shared_ctx = SharedContext(env=dict(os.environ))
            session = Session(shared_ctx=shared_ctx, root_group=root_group)
            return handle_task_ui(root_group, node, session, url, residual_args)
        elif isinstance(node, AnyGroup):
            return handle_group_info_ui(root_group, node, url)
        raise HTTPException(status_code=404, detail="Not Found")

    @app.get("/api/{path:path}", response_model=SessionStateLog | SessionStateLogList)
    async def get_session(path: str, query_params: Dict[str, Any] = {}):
        args = path.split("/")
        node, _, residual_args = extract_node_from_args(root_group, args)
        if isinstance(node, AnyTask) and residual_args:
            if residual_args[0] == "list":
                task_path = get_node_path(root_group, node)
                return list_sessions(task_path, query_params)
            else:
                return read_session(residual_args[0])
        raise HTTPException(status_code=404, detail="Not Found")

    @app.post("/api/{path:path}")
    async def create_new_session(path: str, request: Request = None):
        args = path.split("/")
        node, _, residual_args = extract_node_from_args(root_group, args)
        if isinstance(node, AnyTask):
            session_name = residual_args[0] if residual_args else None
            if not session_name:
                body = await request.json()
                shared_ctx = SharedContext(env=dict(os.environ))
                session = Session(shared_ctx=shared_ctx, root_group=root_group)
                asyncio.create_task(node.async_run(session, str_kwargs=body))
                return {"session_name": session.name}
        raise HTTPException(status_code=404, detail="Not Found")

    def list_sessions(
        task_path: List[str], query_params: Dict[str, Any]
    ) -> SessionStateLogList:
        max_start_time = datetime.now()
        if "to" in query_params:
            max_start_time = datetime.strptime(query_params["to"], "%Y-%m-%d %H:%M:%S")
        min_start_time = max_start_time - timedelta(hours=1)
        if "from" in query_params:
            min_start_time = datetime.strptime(
                query_params["from"], "%Y-%m-%d %H:%M:%S"
            )
        page = int(query_params.get("page", 0))
        limit = int(query_params.get("limit", 10))
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

    config = Config(app=app, host="0.0.0.0", port=port, loop="asyncio")
    server = Server(config)
    # Run the server
    await server.serve()
