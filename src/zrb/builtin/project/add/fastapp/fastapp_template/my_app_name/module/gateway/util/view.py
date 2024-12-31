import os
from typing import Any

from fastapi.responses import HTMLResponse
from my_app_name.common.util.view import render_page, render_str
from my_app_name.config import (
    APP_GATEWAY_CSS_PATH_LIST,
    APP_GATEWAY_FAVICON_PATH,
    APP_GATEWAY_JS_PATH_LIST,
    APP_GATEWAY_LOGO_PATH,
    APP_GATEWAY_SUBTITLE,
    APP_GATEWAY_TITLE,
    APP_GATEWAY_VIEW_DEFAULT_TEMPLATE_PATH,
    APP_GATEWAY_VIEW_PATH,
)

_DEFAULT_TEMPLATE_PATH = os.path.join(
    APP_GATEWAY_VIEW_PATH, APP_GATEWAY_VIEW_DEFAULT_TEMPLATE_PATH
)
_DEFAULT_ERROR_TEMPLATE_PATH = os.path.join(
    APP_GATEWAY_VIEW_PATH, "content", "error.html"
)

_DEFAULT_PARTIALS = {
    "title": APP_GATEWAY_TITLE,
    "subtitle": APP_GATEWAY_SUBTITLE,
    "logo_path": APP_GATEWAY_LOGO_PATH,
    "favicon_path": APP_GATEWAY_FAVICON_PATH,
    "css_path_list": APP_GATEWAY_CSS_PATH_LIST,
    "js_path_list": APP_GATEWAY_JS_PATH_LIST,
}


def render(
    view_path: str,
    template_path: str = _DEFAULT_TEMPLATE_PATH,
    status_code: int = 200,
    headers: dict[str, str] = None,
    media_type: str | None = None,
    partials: dict[str, Any] = {},
    **data: Any
) -> HTMLResponse:
    rendered_partials = {key: val for key, val in _DEFAULT_PARTIALS.items()}
    for key, val in partials.items():
        rendered_partials[key] = val
    return render_page(
        template_path=template_path,
        status_code=status_code,
        headers=headers,
        media_type=media_type,
        partials=rendered_partials,
        content=render_str(template_path=view_path, **data),
    )


def render_error(
    error_message: str,
    status_code: int = 500,
    view_path: str = _DEFAULT_ERROR_TEMPLATE_PATH,
    template_path: str = _DEFAULT_TEMPLATE_PATH,
    headers: dict[str, str] = None,
    media_type: str | None = None,
    partials: dict[str, Any] = {},
):
    return render(
        view_path=view_path,
        template_path=template_path,
        status_code=status_code,
        headers=headers,
        media_type=media_type,
        partials=partials,
        error_status_code=status_code,
        error_message=error_message,
    )
