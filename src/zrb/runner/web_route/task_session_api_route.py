import asyncio
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from zrb.config.config import CFG
from zrb.config.web_auth_config import WebAuthConfig
from zrb.context.shared_context import SharedContext
from zrb.group.any_group import AnyGroup, NodeNotFoundError
from zrb.runner.web_schema.session import NewSessionResponse
from zrb.runner.web_util.user import get_user_from_request
from zrb.session.session import Session
from zrb.session_state_log.session_state_log import SessionStateLog, SessionStateLogList
from zrb.session_state_logger.any_session_state_logger import AnySessionStateLogger
from zrb.task.any_task import AnyTask

if TYPE_CHECKING:
    from fastapi import FastAPI


def serve_task_session_api(
    app: "FastAPI",
    root_group: AnyGroup,
    web_auth_config: WebAuthConfig,
    session_state_logger: AnySessionStateLogger,
    coroutines: list,
) -> None:
    # lazy: heavy third-party
    from fastapi import Query, Request
    from fastapi.responses import JSONResponse

    @app.post("/api/v1/task-sessions/{path:path}")
    async def create_new_task_session_api(
        path: str,
        request: Request,
        inputs: dict[str, Any],
    ) -> "NewSessionResponse":
        """
        Creating new session
        """
        user = await get_user_from_request(web_auth_config, request)
        args = path.strip("/").split("/")
        try:
            task, _, residual_args = root_group.extract_node(args)
        except NodeNotFoundError:
            # FastAPI returns the Response directly; the model annotation only
            # drives response_model for the success path.
            return JSONResponse(
                content={"detail": "Not found"}, status_code=404
            )  # pyright: ignore[reportReturnType]
        if isinstance(task, AnyTask):
            if not user.can_access_task(task):
                return JSONResponse(
                    content={"detail": "Forbidden"}, status_code=403
                )  # pyright: ignore[reportReturnType]
            session_name = residual_args[0] if residual_args else None
            if not session_name:
                shared_ctx = SharedContext(is_web_mode=True)
                session = Session(shared_ctx=shared_ctx, root_group=root_group)
                coro = asyncio.create_task(task.async_run(session, str_kwargs=inputs))
                coroutines.append(coro)
                coro.add_done_callback(lambda coro: coroutines.remove(coro))
                return NewSessionResponse(session_name=session.name)
        return JSONResponse(
            content={"detail": "Not found"}, status_code=404
        )  # pyright: ignore[reportReturnType]

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
        limit: int = Query(default=CFG.WEB_TASK_SESSION_PAGE_SIZE, alias="limit"),
    ) -> "SessionStateLog | SessionStateLogList":
        """
        Getting existing session or sessions
        """
        user = await get_user_from_request(web_auth_config, request)
        args = path.strip("/").split("/")
        try:
            task, _, residual_args = root_group.extract_node(args)
        except NodeNotFoundError:
            return JSONResponse(
                content={"detail": "Not found"}, status_code=404
            )  # pyright: ignore[reportReturnType]
        if isinstance(task, AnyTask) and residual_args:
            if not user.can_access_task(task):
                return JSONResponse(
                    content={"detail": "Forbidden"}, status_code=403
                )  # pyright: ignore[reportReturnType]
            if residual_args[0] == "list":
                task_path = root_group.get_node_path(task)
                try:
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
                except ValueError:
                    return JSONResponse(
                        content={
                            "detail": "Invalid 'from'/'to' timestamp; expected "
                            "'YYYY-MM-DD HH:MM:SS'"
                        },
                        status_code=400,
                    )  # pyright: ignore[reportReturnType]
                return sanitize_session_state_log_list(
                    task,
                    session_state_logger.list(
                        task_path or [], min_start_time, max_start_time, page, limit
                    ),
                )
            else:
                session_state_log = read_task_session_state_log(
                    session_state_logger, residual_args[0]
                )
                if session_state_log is None or not session_belongs_to_task(
                    root_group, task, session_state_log
                ):
                    return JSONResponse(
                        content={"detail": "Not found"}, status_code=404
                    )  # pyright: ignore[reportReturnType]
                return sanitize_session_state_log(task, session_state_log)
        return JSONResponse(
            content={"detail": "Not found"}, status_code=404
        )  # pyright: ignore[reportReturnType]


def read_task_session_state_log(
    session_state_logger: AnySessionStateLogger, session_name: str
) -> "SessionStateLog | None":
    """Read a session log, mapping any storage/validation failure to None."""
    try:
        return session_state_logger.read(session_name)
    except (OSError, ValueError):
        # OSError: missing/unreadable file. ValueError covers JSON decode
        # errors and pydantic's ValidationError.
        return None


def session_belongs_to_task(
    root_group: AnyGroup, task: AnyTask, session_state_log: "SessionStateLog"
) -> bool:
    """Check that the log was recorded for the task named in the URL.

    Without this check, anyone authorized for one task could read another
    task's session by guessing its (random) session name.
    """
    return session_state_log.path == (root_group.get_node_path(task) or [])


def sanitize_session_state_log_list(
    task: AnyTask, session_state_log_list: "SessionStateLogList"
) -> "SessionStateLogList":

    return SessionStateLogList(
        total=session_state_log_list.total,
        data=[
            sanitize_session_state_log(task, data)
            for data in session_state_log_list.data
        ],
    )


def sanitize_session_state_log(
    task: AnyTask, session_state_log: "SessionStateLog"
) -> "SessionStateLog":
    """
    In session, we create snake_case aliases of inputs.
    The purpose was to increase ergonomics, so that user can use `input.system_prompt`
    instead of `input["system-prompt"]`
    However, when we serve the session through HTTP API,
    we only want to show the original input names.
    """

    enhanced_inputs = session_state_log.input
    real_inputs = {}
    for real_input in task.inputs:
        real_input_name = real_input.name
        # A foreign/legacy log may lack some of this task's inputs; serve an
        # empty value rather than raising KeyError.
        real_inputs[real_input_name] = enhanced_inputs.get(real_input_name, "")
    return SessionStateLog(
        name=session_state_log.name,
        start_time=session_state_log.start_time,
        main_task_name=session_state_log.main_task_name,
        path=session_state_log.path,
        input=real_inputs,
        final_result=session_state_log.final_result,
        finished=session_state_log.finished,
        log=session_state_log.log,
        task_status=session_state_log.task_status,
    )
