import json

from zrb.config.config import CFG
from zrb.group.any_group import AnyGroup
from zrb.runner.web_route.jinja_env import get_jinja_env
from zrb.runner.web_schema.user import User
from zrb.runner.web_util.html import get_html_auth_link
from zrb.session.any_session import AnySession
from zrb.task.any_task import AnyTask


def show_task_page(
    user: User,
    root_group: AnyGroup,
    task: AnyTask,
    session: AnySession,
    url: str,
    args: list[str],
):
    from fastapi.responses import HTMLResponse

    web_title = CFG.WEB_TITLE if CFG.WEB_TITLE.strip() != "" else root_group.name
    web_jargon = (
        CFG.WEB_JARGON if CFG.WEB_JARGON.strip() != "" else root_group.description
    )
    auth_link = get_html_auth_link(user)
    session.register_task(task)
    ctx = task.get_ctx(session)
    url_parts = url.split("/")
    parent_url = "/".join(url_parts[:-2] + [""])
    session_url_parts = list(url_parts)
    session_url_parts[1] = "api/v1/task-sessions"
    session_api_url = "/".join(session_url_parts)
    input_url_parts = list(url_parts)
    input_url_parts[1] = "api/v1/task-inputs"
    input_api_url = "/".join(input_url_parts)
    ui_url_parts = list(url_parts)
    ui_url_parts[1] = "ui"
    ui_url = "/".join(ui_url_parts)
    session_name = args[0] if len(args) > 0 else ""
    for task_input in task.inputs:
        task_input.update_shared_context(ctx)
    html = (
        get_jinja_env()
        .get_template("node_page/task/view.html")
        .render(
            cfg=CFG,
            web_title=web_title,
            web_jargon=web_jargon,
            name=task.name,
            description=task.description,
            auth_link=auth_link,
            parent_url=parent_url,
            task_inputs=task.inputs,
            ctx=ctx,
            ui_url=ui_url,
            json_cfg=json.dumps(
                {
                    "CURRENT_URL": url,
                    "SESSION_API_URL": session_api_url,
                    "INPUT_API_URL": input_api_url,
                    "UI_URL": ui_url,
                    "SESSION_NAME": session_name,
                    "PAGE": 0,
                }
            ),
        )
    )
    return HTMLResponse(html)
