import os

from zrb.group.any_group import AnyGroup
from zrb.session.any_session import AnySession
from zrb.task.any_task import AnyTask
from zrb.util.file import read_file
from zrb.util.string.format import fstring_format

_DIR = os.path.dirname(__file__)

_VIEW_TEMPLATE = read_file(os.path.join(_DIR, "view.html"))
_TASK_INPUT_TEMPLATE = read_file(os.path.join(_DIR, "partial", "input.html"))
_MAIN_SCRIPT = read_file(os.path.join(_DIR, "partial", "main.js"))
_SHOW_EXISTING_SESSION_SCRIPT = read_file(
    os.path.join(_DIR, "partial", "show-existing-session.js")
)
_VISUALIZE_HISTORY_SCRIPT = read_file(
    os.path.join(_DIR, "partial", "visualize-history.js")
)
_COMMON_UTIL_SCRIPT = read_file(os.path.join(_DIR, "partial", "common-util.js"))


def handle_task_ui(
    root_group: AnyGroup, task: AnyTask, session: AnySession, url: str, args: list[str]
):
    from fastapi.responses import HTMLResponse

    session.register_task(task)
    ctx = task.get_ctx(session)
    url_parts = url.split("/")
    # Assemble parent url
    parent_url_parts = url_parts[:-2] + [""]
    parent_url = "/".join(parent_url_parts)
    # Assemble api url
    api_url_parts = list(url_parts)
    api_url_parts[1] = "api"
    api_url = "/".join(api_url_parts)
    # Assemble ui url
    ui_url_parts = list(api_url_parts)
    ui_url_parts[1] = "ui"
    ui_url = "/".join(ui_url_parts)
    # Assemble task inputs
    input_html_list = []
    for task_input in task.inputs:
        task_input.update_shared_context(ctx)
        input_html_list.append(
            fstring_format(_TASK_INPUT_TEMPLATE, {"task_input": task_input, "ctx": ctx})
        )
    session_name = args[0] if len(args) > 0 else ""
    return HTMLResponse(
        fstring_format(
            _VIEW_TEMPLATE,
            {
                "name": task.name,
                "description": task.description,
                "root_name": root_group.name,
                "root_description": root_group.description,
                "url": url,
                "parent_url": parent_url,
                "task_inputs": "\n".join(input_html_list),
                "api_url": api_url,
                "ui_url": ui_url,
                "main_script": _MAIN_SCRIPT,
                "show_existing_session_script": _SHOW_EXISTING_SESSION_SCRIPT,
                "visualize_history_script": _VISUALIZE_HISTORY_SCRIPT,
                "common_util_script": _COMMON_UTIL_SCRIPT,
                "session_name": session_name,
            },
        )
    )
