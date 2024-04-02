import os

from zrb import CmdTask, runner

from .._group import snake_zrb_package_name_group

CURRENT_DIR = os.path.dirname(__file__)
PKG_AUTOMATE_DIR = os.path.dirname(CURRENT_DIR)
PROJECT_DIR = os.path.dirname(os.path.dirname(PKG_AUTOMATE_DIR))
PKG_RESOURCE_DIR = os.path.join(PROJECT_DIR, "src", "kebab-zrb-package-name")

prepare_snake_zrb_package_name_venv = CmdTask(
    name="prepare-venv",
    description="Prepare human readable zrb package name venv",
    group=snake_zrb_package_name_group,
    cwd=PKG_RESOURCE_DIR,
    cmd_path=[
        os.path.join(PKG_AUTOMATE_DIR, "activate-venv.sh"),
        os.path.join(CURRENT_DIR, "prepare-venv.sh"),
    ],
)
runner.register(prepare_snake_zrb_package_name_venv)
