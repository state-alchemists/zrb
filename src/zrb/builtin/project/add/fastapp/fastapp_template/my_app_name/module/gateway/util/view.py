import os
from typing import Any

import my_app_name.config as CFG
from fastapi.responses import HTMLResponse
from my_app_name.common.util.view import render_page, render_str
from my_app_name.config import (
    APP_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES,
    APP_GATEWAY_CSS_PATH_LIST,
    APP_GATEWAY_FAVICON_PATH,
    APP_GATEWAY_FOOTER,
    APP_GATEWAY_JS_PATH_LIST,
    APP_GATEWAY_LOGO_PATH,
    APP_GATEWAY_PICO_CSS_PATH,
    APP_GATEWAY_SUBTITLE,
    APP_GATEWAY_TITLE,
    APP_GATEWAY_VIEW_DEFAULT_TEMPLATE_PATH,
    APP_GATEWAY_VIEW_PATH,
)
from my_app_name.module.gateway.config.navigation import APP_NAVIGATION
from my_app_name.schema.user import AuthUserResponse

_DEFAULT_TEMPLATE_PATH = os.path.join(
    APP_GATEWAY_VIEW_PATH, APP_GATEWAY_VIEW_DEFAULT_TEMPLATE_PATH
)
_DEFAULT_ERROR_TEMPLATE_PATH = os.path.join(
    APP_GATEWAY_VIEW_PATH, "content", "error.html"
)

_DEFAULT_PARTIALS = {
    "title": APP_GATEWAY_TITLE,
    "subtitle": APP_GATEWAY_SUBTITLE,
    "footer": APP_GATEWAY_FOOTER,
    "logo_path": APP_GATEWAY_LOGO_PATH,
    "favicon_path": APP_GATEWAY_FAVICON_PATH,
    "pico_css_path": APP_GATEWAY_PICO_CSS_PATH,
    "css_path_list": APP_GATEWAY_CSS_PATH_LIST,
    "js_path_list": APP_GATEWAY_JS_PATH_LIST,
    "show_user_info": True,
    "should_refresh_session": True,
    "refresh_session_interval_seconds": f"{APP_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES * 60 / 3}",
}


def render_content(
    view_path: str,
    template_path: str = _DEFAULT_TEMPLATE_PATH,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
    media_type: str | None = None,
    current_user: AuthUserResponse | None = None,
    page_name: str | None = None,
    partials: dict[str, Any] = {},
    **data: Any,
) -> HTMLResponse:
    rendered_partials = {key: val for key, val in _DEFAULT_PARTIALS.items()}
    for key, val in partials.items():
        rendered_partials[key] = val
    rendered_partials["page_name"] = page_name
    rendered_partials["current_user"] = current_user
    rendered_partials["navigations"] = APP_NAVIGATION.get_accessible_items(
        page_name, current_user
    )
    return render_page(
        template_path=template_path,
        status_code=status_code,
        headers=headers,
        media_type=media_type,
        content=render_str(
            template_path=os.path.join(APP_GATEWAY_VIEW_PATH, "content", view_path),
            **data,
        ),
        **rendered_partials,
    )


def render_error(
    error_message: str,
    status_code: int = 500,
    view_path: str = _DEFAULT_ERROR_TEMPLATE_PATH,
    template_path: str = _DEFAULT_TEMPLATE_PATH,
    headers: dict[str, str] | None = None,
    media_type: str | None = None,
    current_user: AuthUserResponse | None = None,
    page_name: str | None = None,
    partials: dict[str, Any] = {},
):
    return render_content(
        view_path=view_path,
        template_path=template_path,
        status_code=status_code,
        headers=headers,
        media_type=media_type,
        current_user=current_user,
        page_name=page_name,
        partials={"show_user_info": False, **partials},
        error_status_code=status_code,
        error_message=error_message,
    )
