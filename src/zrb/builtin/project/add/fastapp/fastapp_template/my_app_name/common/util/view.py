import os
from typing import Any

from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader


def render_str(template_path: str, **data: Any) -> str:
    """
    Renders a Jinja2 template with the given data.

    :param template_path: The absolute or relative file path of the template.
    :param data: A dictionary of data to pass to the template (default is None).
    :return: Rendered template as a string.
    """
    if data is None:
        data = {}
    # Get the directory and file name
    directory, template_name = os.path.split(template_path)
    # Set up Jinja2 environment with the specific directory
    env = Environment(loader=FileSystemLoader(directory))
    # Render the template
    template = env.get_template(template_name)
    return template.render(data)


def render_page(
    template_path: str,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
    media_type: str | None = None,
    **data: Any
) -> HTMLResponse:
    content = render_str(template_path, **data)
    return HTMLResponse(
        content=content, status_code=status_code, headers=headers, media_type=media_type
    )
