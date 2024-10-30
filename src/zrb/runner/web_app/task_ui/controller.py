from ..any_request_handler import AnyRequestHandler
from ....group.any_group import AnyGroup
from ....task.any_task import AnyTask
from ....util.string.format import fstring_format
from ....context.shared_context import SharedContext
from ....session.session import Session

import os

_DIR = os.path.dirname(__file__)

with open(os.path.join(_DIR, "view.html"), "r") as f:
    _VIEW_TEMPLATE = f.read()

with open(os.path.join(_DIR, "partial", "input.html")) as f:
    _TASK_INPUT_TEMPLATE = f.read()

with open(os.path.join(_DIR, "partial", "script.js")) as f:
    _SCRIPT = f.read()


def handle_task_ui(
    handler: AnyRequestHandler, root_group: AnyGroup, task: AnyTask, url: str, args: list[str]
):
    shared_ctx = SharedContext(env={key: val for key, val in os.environ.items()})
    session = Session(shared_ctx=shared_ctx)
    session.register_task(task)
    ctx = session.get_ctx(task)
    url_parts = url.split("/")
    # Assemble parent url
    parent_url_parts = url_parts[:-2] + [""]
    parent_url = "/".join(parent_url_parts)
    # Assemble api url
    api_url_parts = list(url_parts)
    api_url_parts[1] = "api"
    api_url = "/".join(api_url_parts)
    task_inputs = "\n".join([
        fstring_format(_TASK_INPUT_TEMPLATE, {"task_input": task_input, "ctx": ctx})
        for task_input in task.inputs
    ])
    session_name = args[0] if len(args) > 0 else None
    handler.send_html_response(fstring_format(
        _VIEW_TEMPLATE, {
            "name": task.name,
            "description": task.description,
            "root_name": root_group.name,
            "root_description": root_group.description,
            "url": url,
            "parent_url": parent_url,
            "task_inputs": task_inputs,
            "api_url": api_url,
            "script": _SCRIPT,
            "session_name": session_name
        }
    ))
