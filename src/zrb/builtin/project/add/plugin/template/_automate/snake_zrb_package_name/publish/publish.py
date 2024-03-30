import os

from zrb import CmdTask, runner
from ..._project import publish_project
from .._group import kebab_zrb_package_name_group
from ..build import build_snake_zrb_package_name

CURRENT_DIR = os.path.dirname(__file__)
AUTOMATE_DIR = os.path.dirname(CURRENT_DIR)
PROJECT_DIR = os.path.dirname(os.path.dirname(AUTOMATE_DIR))
RESOURCE_DIR = os.path.join(PROJECT_DIR, "src", "kebab-zrb-package-name")

publish_snake_zrb_package_name = CmdTask(
    name="publish",
    description="Publish human readable zrb package name",
    group=kebab_zrb_package_name_group,
    upstreams=[build_snake_zrb_package_name],
    cwd=RESOURCE_DIR,
    cmd_path=[
        os.path.join(AUTOMATE_DIR, "activate-venv.sh"),
        os.path.join(CURRENT_DIR, "publish.sh"),
    ],
)

publish_snake_zrb_package_name >> publish_project

runner.register(publish_snake_zrb_package_name)
