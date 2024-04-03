import os

from zrb import CmdTask, runner

from .._group import snake_zrb_package_name_group

_CURRENT_DIR = os.path.dirname(__file__)
_PKG_AUTOMATE_DIR = os.path.dirname(_CURRENT_DIR)
_PROJECT_DIR = os.path.dirname(os.path.dirname(_PKG_AUTOMATE_DIR))
_PKG_RESOURCE_DIR = os.path.join(_PROJECT_DIR, "src", "kebab-zrb-package-name")

prepare_snake_zrb_package_name_venv = CmdTask(
    name="prepare-venv",
    description="Prepare human readable zrb package name venv",
    group=snake_zrb_package_name_group,
    cwd=_PKG_RESOURCE_DIR,
    cmd_path=[
        os.path.join(_PKG_AUTOMATE_DIR, "activate-venv.sh"),
        os.path.join(_CURRENT_DIR, "prepare-venv.sh"),
    ],
)
runner.register(prepare_snake_zrb_package_name_venv)
