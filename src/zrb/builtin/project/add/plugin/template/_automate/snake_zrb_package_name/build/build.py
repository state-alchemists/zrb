import os

from zrb import CmdTask, runner
from ..._project import build_project
from .._group import snake_zrb_package_name_group
from ..prepare_venv import prepare_snake_zrb_package_name_venv

_CURRENT_DIR = os.path.dirname(__file__)
_PKG_AUTOMATE_DIR = os.path.dirname(_CURRENT_DIR)
_PROJECT_DIR = os.path.dirname(os.path.dirname(_PKG_AUTOMATE_DIR))
_PKG_RESOURCE_DIR = os.path.join(_PROJECT_DIR, "src", "kebab-zrb-package-name")

build_snake_zrb_package_name = CmdTask(
    name="build",
    description="Build human readable zrb package name",
    group=snake_zrb_package_name_group,
    upstreams=[prepare_snake_zrb_package_name_venv],
    cwd=_PKG_RESOURCE_DIR,
    cmd_path=[
        os.path.join(_PKG_AUTOMATE_DIR, "activate-venv.sh"),
        os.path.join(_CURRENT_DIR, "build.sh"),
    ],
)

build_snake_zrb_package_name >> build_project

runner.register(build_snake_zrb_package_name)
