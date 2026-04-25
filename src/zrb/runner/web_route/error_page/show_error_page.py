from zrb.config.config import CFG
from zrb.group.any_group import AnyGroup
from zrb.runner.web_route.jinja_env import get_jinja_env
from zrb.runner.web_schema.user import User
from zrb.runner.web_util.html import get_html_auth_link


def show_error_page(user: User, root_group: AnyGroup, status_code: int, message: str):
    from fastapi.responses import HTMLResponse

    web_title = CFG.WEB_TITLE if CFG.WEB_TITLE.strip() != "" else root_group.name
    auth_link = get_html_auth_link(user)
    html = (
        get_jinja_env()
        .get_template("error_page/view.html")
        .render(
            cfg=CFG,
            web_title=web_title,
            name=root_group.name,
            description=root_group.description,
            auth_link=auth_link,
            error_status_code=status_code,
            error_message=message,
        )
    )
    return HTMLResponse(html, status_code=status_code)
