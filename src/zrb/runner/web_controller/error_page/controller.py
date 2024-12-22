import os

from fastapi.responses import HTMLResponse

from zrb.group.any_group import AnyGroup
from zrb.util.file import read_file
from zrb.util.string.format import fstring_format

_DIR = os.path.dirname(__file__)
_VIEW_TEMPLATE = read_file(os.path.join(_DIR, "view.html"))


def show_error_page(root_group: AnyGroup, status_code: int, message: str):
    return HTMLResponse(
        fstring_format(
            _VIEW_TEMPLATE,
            {
                "name": root_group.name,
                "description": root_group.description,
                "error_status_code": status_code,
                "error_message": message,
            },
        )
    )
