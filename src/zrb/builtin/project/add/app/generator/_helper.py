import os

from zrb.helper.util import to_kebab_case, to_snake_case
from zrb.helper.typecheck import typechecked


@typechecked
def validate_existing_package(project_dir: str, package_name: str):
    kebab_package_name = to_kebab_case(package_name)
    snake_package_name = to_snake_case(package_name)
    package_init_path = os.path.join(
        project_dir, "src", kebab_package_name, "src", snake_package_name, "__init__.py"
    )
    if not os.path.isfile(package_init_path):
        raise Exception(f"Package not exists: {package_init_path}")
