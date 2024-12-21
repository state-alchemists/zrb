import json
import os

from zrb.group.any_group import AnyGroup
from zrb.session.any_session import AnySession
from zrb.task.any_task import AnyTask
from zrb.util.file import read_file
from zrb.util.string.format import fstring_format

_DIR = os.path.dirname(__file__)

_VIEW_TEMPLATE = read_file(os.path.join(_DIR, "view.html"))
_TASK_INPUT_TEMPLATE = read_file(os.path.join(_DIR, "partial", "input.html"))


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
    # Assemble session api url
    session_url_parts = list(url_parts)
    session_url_parts[1] = "api/sessions"
    session_api_url = "/".join(session_url_parts)
    # Assemble input api url
    input_url_parts = list(url_parts)
    input_url_parts[1] = "api/inputs"
    input_api_url = "/".join(input_url_parts)
    # Assemble ui url
    ui_url_parts = list(url_parts)
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
                "ui_url": ui_url,
                "json_cfg": json.dumps(
                    {
                        "CURRENT_URL": url,
                        "SESSION_API_URL": session_api_url,
                        "INPUT_API_URL": input_api_url,
                        "UI_URL": ui_url,
                        "SESSION_NAME": session_name,
                        "PAGE": 0,
                    }
                ),
            },
        )
    )
