import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Annotated

from zrb.config import BANNER, VERSION
from zrb.context.shared_context import SharedContext
from zrb.group.any_group import AnyGroup
from zrb.runner.common_util import get_run_kwargs
from zrb.runner.web_config.config import WebConfig
from zrb.runner.web_route.docs.docs_route import serve_docs
from zrb.runner.web_route.error_page.controller import show_error_page
from zrb.runner.web_route.group_info_page.controller import show_group_info_page
from zrb.runner.web_route.home_page.controller import show_home_page
from zrb.runner.web_route.login_page.controller import show_login_page
from zrb.runner.web_route.logout_page.controller import show_logout_page
from zrb.runner.web_route.session_page.controller import show_session_page
from zrb.runner.web_route.static.static_route import serve_static_resources
from zrb.runner.web_schema.session import NewSessionResponse
from zrb.runner.web_schema.token import RefreshTokenRequest, Token
from zrb.runner.web_util.token import generate_tokens_by_credentials, regenerate_tokens
from zrb.runner.web_util.user import get_user_from_request
from zrb.session.session import Session
from zrb.session_state_log.session_state_log import SessionStateLog, SessionStateLogList
from zrb.session_state_logger.any_session_state_logger import AnySessionStateLogger
from zrb.task.any_task import AnyTask
from zrb.util.group import NodeNotFoundError, extract_node_from_args, get_node_path

if TYPE_CHECKING:
    # We want fastapi to only be loaded when necessary to decrease footprint
    from fastapi import FastAPI


def create_web_app(
    root_group: AnyGroup,
    web_config: WebConfig,
    session_state_logger: AnySessionStateLogger,
) -> "FastAPI":
    from contextlib import asynccontextmanager

    from fastapi import (
        Cookie,
        Depends,
        FastAPI,
        HTTPException,
        Query,
        Request,
        Response,
    )
    from fastapi.responses import HTMLResponse
    from fastapi.security import OAuth2PasswordRequestForm

    _COROS = []

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        for line in BANNER.split("\n") + [
            f"Zrb Server running on http://localhost:{web_config.port}"
        ]:
            print(line, file=sys.stderr)
        yield
        for coro in _COROS:
            coro.cancel()
        asyncio.gather(*_COROS)

    app = FastAPI(
        title="Zrb",
        version=VERSION,
        summary="Your Automation Powerhouse",
        lifespan=lifespan,
        docs_url=None,
    )

    serve_static_resources(app, web_config)
    serve_docs(app)

    # Serve homepage
    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/ui", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/ui/", response_class=HTMLResponse, include_in_schema=False)
    async def home_page_ui(request: Request) -> HTMLResponse:
        user = await get_user_from_request(web_config, request)
        return show_home_page(user, root_group)

    @app.get("/ui/{path:path}", response_class=HTMLResponse, include_in_schema=False)
    async def ui_page(path: str, request: Request) -> HTMLResponse:
        user = await get_user_from_request(web_config, request)
        # Avoid capturing '/ui' itself
        if not path:
            return show_error_page(user, root_group, 422, "Undefined path")
        args = path.strip("/").split("/")
        try:
            node, node_path, residual_args = extract_node_from_args(root_group, args)
        except NodeNotFoundError as e:
            return show_error_page(user, root_group, 404, str(e))
        url = f"/ui/{'/'.join(node_path)}/"
        if isinstance(node, AnyTask):
            if not user.can_access_task(node):
                return show_error_page(user, root_group, 403, "Forbidden")
            shared_ctx = SharedContext(env=dict(os.environ))
            session = Session(shared_ctx=shared_ctx, root_group=root_group)
            return show_session_page(
                user, root_group, node, session, url, residual_args
            )
        elif isinstance(node, AnyGroup):
            if not user.can_access_group(node):
                return show_error_page(user, root_group, 403, "Forbidden")
            return show_group_info_page(user, root_group, node, url)
        return show_error_page(user, root_group, 404, "Not found")

    @app.get("/login", response_class=HTMLResponse, include_in_schema=False)
    async def login(request: Request) -> HTMLResponse:
        user = await get_user_from_request(web_config, request)
        return show_login_page(user, root_group)

    @app.get("/logout", response_class=HTMLResponse, include_in_schema=False)
    async def logout(request: Request) -> HTMLResponse:
        user = await get_user_from_request(web_config, request)
        return show_logout_page(user, root_group)

    @app.post("/api/v1/login")
    async def login_api(
        response: Response, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
    ):
        token = generate_tokens_by_credentials(
            web_config=web_config,
            username=form_data.username,
            password=form_data.password,
        )
        if token is None:
            raise HTTPException(
                status_code=400, detail="Incorrect username or password"
            )
        _set_auth_cookie(response, token)
        return token

    @app.post("/api/v1/refresh-token")
    async def refresh_token_api(
        response: Response,
        body: RefreshTokenRequest = None,
        refresh_token_cookie: str = Cookie(
            None, alias=web_config.refresh_token_cookie_name
        ),
    ):
        # Try to get the refresh token from the request body first
        refresh_token = body.refresh_token if body else None
        # If not in the body, try to get it from the cookie
        if not refresh_token:
            refresh_token = refresh_token_cookie
        # If we still don't have a refresh token, raise an exception
        if not refresh_token:
            raise HTTPException(status_code=400, detail="Refresh token not provided")
        # Get token
        new_token = regenerate_tokens(web_config, refresh_token)
        _set_auth_cookie(response, new_token)
        return new_token

    def _set_auth_cookie(response: Response, token: Token):
        access_token_max_age = web_config.access_token_expire_minutes * 60
        refresh_token_max_age = web_config.refresh_token_expire_minutes * 60
        now = datetime.now(timezone.utc)
        response.set_cookie(
            key=web_config.access_token_cookie_name,
            value=token.access_token,
            httponly=True,
            max_age=access_token_max_age,
            expires=now + timedelta(seconds=access_token_max_age),
        )
        response.set_cookie(
            key=web_config.refresh_token_cookie_name,
            value=token.refresh_token,
            httponly=True,
            max_age=refresh_token_max_age,
            expires=now + timedelta(seconds=refresh_token_max_age),
        )

    @app.get("/api/v1/logout")
    @app.post("/api/v1/logout")
    async def logout_api(response: Response):
        response.delete_cookie(web_config.access_token_cookie_name)
        response.delete_cookie(web_config.refresh_token_cookie_name)
        return {"message": "Logout successful"}

    @app.post("/api/v1/task-sessions/{path:path}")
    async def create_new_task_session_api(
        path: str,
        request: Request,
    ) -> NewSessionResponse:
        """
        Creating new session
        """
        user = await get_user_from_request(web_config, request)
        args = path.strip("/").split("/")
        task, _, residual_args = extract_node_from_args(root_group, args)
        if isinstance(task, AnyTask):
            if not user.can_access_task(task):
                raise HTTPException(status_code=403)
            session_name = residual_args[0] if residual_args else None
            if not session_name:
                body = await request.json()
                shared_ctx = SharedContext(env=dict(os.environ))
                session = Session(shared_ctx=shared_ctx, root_group=root_group)
                coro = asyncio.create_task(task.async_run(session, str_kwargs=body))
                _COROS.append(coro)
                coro.add_done_callback(lambda coro: _COROS.remove(coro))
                return NewSessionResponse(session_name=session.name)
        raise HTTPException(status_code=404)

    @app.get("/api/v1/task-inputs/{path:path}", response_model=dict[str, str])
    async def get_default_inputs_api(
        path: str,
        request: Request,
        query: str = Query("{}", description="JSON encoded inputs"),
    ) -> dict[str, str]:
        """
        Getting input completion for path
        """
        user = await get_user_from_request(web_config, request)
        args = path.strip("/").split("/")
        task, _, _ = extract_node_from_args(root_group, args)
        if isinstance(task, AnyTask):
            if not user.can_access_task(task):
                raise HTTPException(status_code=403)
            query_dict = json.loads(query)
            run_kwargs = get_run_kwargs(
                task=task, args=[], kwargs=query_dict, prompt=False
            )
            return run_kwargs
        raise HTTPException(status_code=404, detail="Not Found")

    @app.get(
        "/api/v1/task-sessions/{path:path}",
        response_model=SessionStateLog | SessionStateLogList,
    )
    async def get_session_api(
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
        task, _, residual_args = extract_node_from_args(root_group, args)
        if isinstance(task, AnyTask) and residual_args:
            if not user.can_access_task(task):
                raise HTTPException(status_code=403)
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
        raise HTTPException(status_code=404, detail="Not Found")

    return app
