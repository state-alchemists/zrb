import os

from zrb.helper.string.parse_replacement import parse_replacement
from zrb.helper.util import to_kebab_case


def replace_marker(text: str, marker: str, code: str) -> str:
    return parse_replacement(text, {marker: "\n".join([code, marker])})


def get_app_frontend_routes_dir(project_dir: str, app_name: str) -> str:
    return os.path.join(
        get_app_dir(project_dir, app_name), "src", "frontend", "src", "routes"
    )


def get_app_dir(project_dir: str, app_name: str) -> str:
    kebab_app_name = to_kebab_case(app_name)
    return os.path.join(project_dir, "src", kebab_app_name)
