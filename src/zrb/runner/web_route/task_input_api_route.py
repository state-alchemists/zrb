import json
from typing import TYPE_CHECKING

from zrb.config.web_auth_config import WebAuthConfig
from zrb.group.any_group import AnyGroup
from zrb.runner.common_util import get_task_str_kwargs
from zrb.runner.web_util.task_lookup import create_error_response, find_task
from zrb.runner.web_util.user import get_user_from_request

if TYPE_CHECKING:
    from fastapi import FastAPI


def serve_task_input_api(
    app: "FastAPI",
    root_group: AnyGroup,
    web_auth_config: WebAuthConfig,
) -> None:
    # lazy: heavy third-party
    from fastapi import Query, Request

    @app.get("/api/v1/task-inputs/{path:path}", response_model=dict[str, str])
    async def get_default_inputs_api(
        path: str,
        request: Request,
        query: str = Query("{}", description="JSON encoded inputs"),
    ) -> "dict[str, str]":
        """
        Getting input completion for path
        """
        user = await get_user_from_request(web_auth_config, request)
        found = find_task(root_group, path)
        if found is None:
            return create_error_response(404)  # pyright: ignore[reportReturnType]
        task, _ = found
        if not user.can_access_task(task):
            return create_error_response(403)  # pyright: ignore[reportReturnType]
        try:
            str_kwargs = json.loads(query)
        except json.JSONDecodeError:
            return create_error_response(
                400, "Invalid 'query' parameter; expected JSON"
            )  # pyright: ignore[reportReturnType]
        return get_task_str_kwargs(
            task=task, str_args=[], str_kwargs=str_kwargs, cli_mode=False
        )
