import os

from zrb.group.any_group import AnyGroup
from zrb.runner.web_schema.user import User
from zrb.runner.web_util.html import get_html_auth_link
from zrb.util.file import read_file
from zrb.util.string.format import fstring_format


def show_error_page(user: User, root_group: AnyGroup, status_code: int, message: str):
    from fastapi.responses import HTMLResponse

    _DIR = os.path.dirname(__file__)
    _VIEW_TEMPLATE = read_file(os.path.join(_DIR, "view.html"))
    auth_link = get_html_auth_link(user)
    return HTMLResponse(
        fstring_format(
            _VIEW_TEMPLATE,
            {
                "name": root_group.name,
                "description": root_group.description,
                "auth_link": auth_link,
                "error_status_code": status_code,
                "error_message": message,
            },
        ),
        status_code=status_code,
    )
