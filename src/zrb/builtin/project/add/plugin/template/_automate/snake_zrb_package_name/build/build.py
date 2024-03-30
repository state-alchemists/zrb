import os

from zrb import CmdTask, runner
from ..._project import build_project
from .._group import kebab_zrb_package_name_group
from ..prepare_venv import prepare_snake_zrb_package_name_venv

CURRENT_DIR = os.path.dirname(__file__)
PKG_AUTOMATE_DIR = os.path.dirname(CURRENT_DIR)
PROJECT_DIR = os.path.dirname(os.path.dirname(PKG_AUTOMATE_DIR))
PKG_RESOURCE_DIR = os.path.join(PROJECT_DIR, "src", "kebab-zrb-package-name")

build_snake_zrb_package_name = CmdTask(
    name="build",
    description="Build human readable zrb package name",
    group=kebab_zrb_package_name_group,
    upstreams=[prepare_snake_zrb_package_name_venv],
    cwd=PKG_RESOURCE_DIR,
    cmd_path=[
        os.path.join(PKG_AUTOMATE_DIR, "activate-venv.sh"),
        os.path.join(CURRENT_DIR, "build.sh"),
    ],
)

build_snake_zrb_package_name >> build_project

runner.register(build_snake_zrb_package_name)
