from zrb.config.config import CFG
from zrb.group.any_group import AnyGroup
from zrb.runner.web_route.jinja_env import get_jinja_env
from zrb.runner.web_schema.user import User
from zrb.runner.web_util.html import (
    get_html_auth_link,
    get_html_subgroup_info,
    get_html_subtask_info,
)


def show_group_page(user: User, root_group: AnyGroup, group: AnyGroup, url: str):
    from fastapi.responses import HTMLResponse

    web_title = CFG.WEB_TITLE if CFG.WEB_TITLE.strip() != "" else root_group.name
    web_jargon = (
        CFG.WEB_JARGON if CFG.WEB_JARGON.strip() != "" else root_group.description
    )
    url_parts = url.split("/")
    parent_url = "/".join(url_parts[:-2] + [""])
    group_info = get_html_subgroup_info(user, url, group)
    task_info = get_html_subtask_info(user, url, group)
    auth_link = get_html_auth_link(user)
    html = (
        get_jinja_env()
        .get_template("node_page/group/view.html")
        .render(
            cfg=CFG,
            web_title=web_title,
            web_jargon=web_jargon,
            group_info=group_info,
            task_info=task_info,
            name=group.name,
            description=group.description,
            auth_link=auth_link,
            parent_url=parent_url,
        )
    )
    return HTMLResponse(html)
