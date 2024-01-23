import os

from zrb import CmdTask, StrInput, runner
from zrb.builtin.group import project_group

CURRENT_DIR = os.path.dirname(__file__)
PROJECT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
RESOURCE_DIR = os.path.join(PROJECT_DIR, "src", "kebab-zrb-package-name")
PACKAGE_DIR = os.path.join(RESOURCE_DIR, "src")

###############################################################################
# ⚙️ prepare-kebab-zrb-package-name
###############################################################################

prepare_snake_zrb_package_name = CmdTask(
    name="prepare-kebab-zrb-package-name",
    description="Prepare venv for human readable zrb package name",
    group=project_group,
    cwd=RESOURCE_DIR,
    cmd_path=[
        os.path.join(CURRENT_DIR, "cmd", "activate-venv.sh"),
        os.path.join(CURRENT_DIR, "cmd", "prepare-venv.sh"),
    ],
)
runner.register(prepare_snake_zrb_package_name)

###############################################################################
# ⚙️ build-kebab-zrb-package-name
###############################################################################

build_snake_zrb_package_name = CmdTask(
    name="build-kebab-zrb-package-name",
    description="Build human readable zrb package name",
    group=project_group,
    upstreams=[prepare_snake_zrb_package_name],
    cwd=RESOURCE_DIR,
    cmd_path=[
        os.path.join(CURRENT_DIR, "cmd", "activate-venv.sh"),
        os.path.join(CURRENT_DIR, "cmd", "build.sh"),
    ],
)
runner.register(build_snake_zrb_package_name)

###############################################################################
# ⚙️ publish-kebab-zrb-package-name
###############################################################################

publish_snake_zrb_package_name = CmdTask(
    name="publish-kebab-zrb-package-name",
    description="Publish human readable zrb package name",
    group=project_group,
    inputs=[
        StrInput(
            name="kebab-zrb-package-name-repo",
            prompt="Pypi repository for human readable zrb package name",
            description="Pypi repository for human readalbe zrb package name",
            default="pypi",
        )
    ],
    upstreams=[build_snake_zrb_package_name],
    cwd=RESOURCE_DIR,
    cmd_path=[
        os.path.join(CURRENT_DIR, "cmd", "activate-venv.sh"),
        os.path.join(CURRENT_DIR, "cmd", "publish.sh"),
    ],
)
runner.register(publish_snake_zrb_package_name)

###############################################################################
# ⚙️ install-kebab-zrb-package-name-symlink
###############################################################################

install_snake_zrb_package_name_symlink = CmdTask(
    name="install-kebab-zrb-package-name-symlink",
    description="Install human readable zrb package name as symlink",
    group=project_group,
    upstreams=[build_snake_zrb_package_name],
    cwd=RESOURCE_DIR,
    cmd_path=[
        os.path.join(CURRENT_DIR, "cmd", "activate-venv.sh"),
        os.path.join(CURRENT_DIR, "cmd", "install-symlink.sh"),
    ],
)
runner.register(install_snake_zrb_package_name_symlink)
