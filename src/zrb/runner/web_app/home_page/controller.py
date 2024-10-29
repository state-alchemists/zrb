from ..any_request_handler import AnyRequestHandler
from ....group.any_group import AnyGroup
from ....util.string.format import fstring_format

import os

_DIR = os.path.dirname(__file__)

with open(os.path.join(_DIR, "view.html"), "r") as f:
    _VIEW_TEMPLATE = f.read()

with open(os.path.join(_DIR, "partial", "group_li.html")) as f:
    _GROUP_LI_TEMPLATE = f.read()

with open(os.path.join(_DIR, "partial", "task_li.html")) as f:
    _TASK_LI_TEMPLATE = f.read()


def handle_home_page(handler: AnyRequestHandler, root_group: AnyGroup):
    data = {
        "group_li": "\n".join([
            fstring_format(
                _GROUP_LI_TEMPLATE, {"caption": name, "description": group.description}
            )
            for name, group in root_group.subgroups.items()
            if group.contain_tasks
        ]),
        "task_li": "\n".join([
            fstring_format(
                _TASK_LI_TEMPLATE, {"caption": name, "description": task.description}
            )
            for name, task in root_group.subtasks.items()
        ]),
        "name": root_group.name,
        "description": root_group.description
    }
    handler.send_html_response(fstring_format(_VIEW_TEMPLATE, data))
