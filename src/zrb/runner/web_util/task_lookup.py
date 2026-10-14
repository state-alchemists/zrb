"""Resolve a task API path to a task, and the JSON error the routes answer with."""

from typing import TYPE_CHECKING

from zrb.group.any_group import AnyGroup, NodeNotFoundError
from zrb.task.any_task import AnyTask

if TYPE_CHECKING:
    from fastapi.responses import JSONResponse

_DETAIL = {403: "Forbidden", 404: "Not found"}


def find_task(root_group: AnyGroup, path: str) -> tuple[AnyTask, list[str]] | None:
    """The task at *path* and its residual args, or None when there is none."""
    try:
        task, _, residual_args = root_group.extract_node(path.strip("/").split("/"))
    except NodeNotFoundError:
        return None
    if not isinstance(task, AnyTask):
        return None
    return task, residual_args


def create_error_response(status_code: int, detail: str = "") -> "JSONResponse":
    # lazy: heavy third-party
    from fastapi.responses import JSONResponse

    return JSONResponse(
        content={"detail": detail or _DETAIL[status_code]}, status_code=status_code
    )
