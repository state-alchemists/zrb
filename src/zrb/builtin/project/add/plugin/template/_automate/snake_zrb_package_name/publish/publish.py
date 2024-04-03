import os

from zrb import CmdTask, runner

from ..._project import publish_project
from .._group import snake_zrb_package_name_group
from ..build import build_snake_zrb_package_name

_CURRENT_DIR = os.path.dirname(__file__)
_PKG_AUTOMATE_DIR = os.path.dirname(_CURRENT_DIR)
_PROJECT_DIR = os.path.dirname(os.path.dirname(_PKG_AUTOMATE_DIR))
_PKG_RESOURCE_DIR = os.path.join(_PROJECT_DIR, "src", "kebab-zrb-package-name")

publish_snake_zrb_package_name = CmdTask(
    name="publish",
    description="Publish human readable zrb package name",
    group=snake_zrb_package_name_group,
    upstreams=[build_snake_zrb_package_name],
    cwd=_PKG_RESOURCE_DIR,
    cmd_path=[
        os.path.join(_PKG_AUTOMATE_DIR, "activate-venv.sh"),
        os.path.join(_CURRENT_DIR, "publish.sh"),
    ],
)

publish_snake_zrb_package_name >> publish_project

runner.register(publish_snake_zrb_package_name)
