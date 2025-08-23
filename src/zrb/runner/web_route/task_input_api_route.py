import json
from typing import TYPE_CHECKING

from zrb.config.web_auth_config import WebAuthConfig
from zrb.group.any_group import AnyGroup
from zrb.runner.common_util import get_task_str_kwargs
from zrb.runner.web_util.user import get_user_from_request
from zrb.task.any_task import AnyTask
from zrb.util.group import NodeNotFoundError, extract_node_from_args

if TYPE_CHECKING:
    # We want fastapi to only be loaded when necessary to decrease footprint
    from fastapi import FastAPI


def serve_task_input_api(
    app: "FastAPI",
    root_group: AnyGroup,
    web_auth_config: WebAuthConfig,
) -> None:
    from fastapi import Query, Request
    from fastapi.responses import JSONResponse

    @app.get("/api/v1/task-inputs/{path:path}", response_model=dict[str, str])
    async def get_default_inputs_api(
        path: str,
        request: Request,
        query: str = Query("{}", description="JSON encoded inputs"),
    ) -> dict[str, str]:
        """
        Getting input completion for path
        """
        user = await get_user_from_request(web_auth_config, request)
        args = path.strip("/").split("/")
        try:
            task, _, _ = extract_node_from_args(root_group, args)
        except NodeNotFoundError:
            return JSONResponse(content={"detail": "Not found"}, status_code=404)
        if isinstance(task, AnyTask):
            if not user.can_access_task(task):
                return JSONResponse(content={"detail": "Forbidden"}, status_code=403)
            str_kwargs = json.loads(query)
            task_str_kwargs = get_task_str_kwargs(
                task=task, str_args=[], str_kwargs=str_kwargs, cli_mode=False
            )
            return task_str_kwargs
        return JSONResponse(content={"detail": "Not found"}, status_code=404)
