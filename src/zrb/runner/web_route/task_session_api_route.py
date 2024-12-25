import asyncio
import os
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from zrb.context.shared_context import SharedContext
from zrb.group.any_group import AnyGroup
from zrb.runner.web_config.config import WebConfig
from zrb.runner.web_schema.session import NewSessionResponse
from zrb.runner.web_util.user import get_user_from_request
from zrb.session.session import Session
from zrb.session_state_log.session_state_log import SessionStateLog, SessionStateLogList
from zrb.session_state_logger.any_session_state_logger import AnySessionStateLogger
from zrb.task.any_task import AnyTask
from zrb.util.group import NodeNotFoundError, extract_node_from_args, get_node_path

if TYPE_CHECKING:
    # We want fastapi to only be loaded when necessary to decrease footprint

    from fastapi import FastAPI


def serve_task_session_api(
    app: "FastAPI",
    root_group: AnyGroup,
    web_config: WebConfig,
    session_state_logger: AnySessionStateLogger,
    coroutines: list,
) -> None:
    from fastapi import Query, Request
    from fastapi.responses import JSONResponse

    @app.post("/api/v1/task-sessions/{path:path}")
    async def create_new_task_session_api(
        path: str,
        request: Request,
        inputs: dict[str, Any],
    ) -> NewSessionResponse:
        """
        Creating new session
        """
        user = await get_user_from_request(web_config, request)
        args = path.strip("/").split("/")
        try:
            task, _, residual_args = extract_node_from_args(root_group, args)
        except NodeNotFoundError:
            return JSONResponse(content={"detail": "Not found"}, status_code=404)
        if isinstance(task, AnyTask):
            if not user.can_access_task(task):
                return JSONResponse(content={"detail": "Forbidden"}, status_code=403)
            session_name = residual_args[0] if residual_args else None
            if not session_name:
                shared_ctx = SharedContext(env=dict(os.environ))
                session = Session(shared_ctx=shared_ctx, root_group=root_group)
                coro = asyncio.create_task(task.async_run(session, str_kwargs=inputs))
                coroutines.append(coro)
                coro.add_done_callback(lambda coro: coroutines.remove(coro))
                return NewSessionResponse(session_name=session.name)
        return JSONResponse(content={"detail": "Not found"}, status_code=404)

    @app.get(
        "/api/v1/task-sessions/{path:path}",
        response_model=SessionStateLog | SessionStateLogList,
    )
    async def get_task_session_api(
        path: str,
        request: Request,
        min_start_query: str = Query(default=None, alias="from"),
        max_start_query: str = Query(default=None, alias="to"),
        page: int = Query(default=0, alias="page"),
        limit: int = Query(default=10, alias="limit"),
    ) -> SessionStateLog | SessionStateLogList:
        """
        Getting existing session or sessions
        """
        user = await get_user_from_request(web_config, request)
        args = path.strip("/").split("/")
        try:
            task, _, residual_args = extract_node_from_args(root_group, args)
        except NodeNotFoundError:
            return JSONResponse(content={"detail": "Not found"}, status_code=404)
        if isinstance(task, AnyTask) and residual_args:
            if not user.can_access_task(task):
                return JSONResponse(content={"detail": "Forbidden"}, status_code=403)
            if residual_args[0] == "list":
                task_path = get_node_path(root_group, task)
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
                return session_state_logger.list(
                    task_path, min_start_time, max_start_time, page, limit
                )
            else:
                return session_state_logger.read(residual_args[0])
        return JSONResponse(content={"detail": "Not found"}, status_code=404)
