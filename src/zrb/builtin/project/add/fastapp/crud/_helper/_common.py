import os

from zrb.helper.util import to_kebab_case


def get_app_module_dir(project_dir: str, app_name: str) -> str:
    kebab_app_name = to_kebab_case(app_name)
    return os.path.join(project_dir, "src", kebab_app_name, "src", "module")
