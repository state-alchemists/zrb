import os
from typing import TYPE_CHECKING

from zrb.context.shared_context import SharedContext
from zrb.group.any_group import AnyGroup
from zrb.runner.web_config.config import WebConfig
from zrb.runner.web_route.error_page.show_error_page import show_error_page
from zrb.runner.web_route.node_page.group.show_group_page import show_group_page
from zrb.runner.web_route.node_page.task.show_task_page import show_task_page
from zrb.runner.web_util.user import get_user_from_request
from zrb.session.session import Session
from zrb.task.any_task import AnyTask
from zrb.util.group import NodeNotFoundError, extract_node_from_args

if TYPE_CHECKING:
    # We want fastapi to only be loaded when necessary to decrease footprint
    from fastapi import FastAPI


def serve_node_page(
    app: "FastAPI",
    root_group: AnyGroup,
    web_config: WebConfig,
) -> None:
    from fastapi import Request
    from fastapi.responses import HTMLResponse

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
            return show_task_page(user, root_group, node, session, url, residual_args)
        elif isinstance(node, AnyGroup):
            if not user.can_access_group(node):
                return show_error_page(user, root_group, 403, "Forbidden")
            return show_group_page(user, root_group, node, url)
        return show_error_page(user, root_group, 404, "Not found")
