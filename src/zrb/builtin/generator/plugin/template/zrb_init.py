import os

from zrb import CmdTask, StrInput, runner
from zrb.builtin.group import plugin_group

PROJECT_DIR = os.path.dirname(__file__)

###############################################################################
# ⚙️ prepare-plugin
###############################################################################

prepare_plugin = CmdTask(
    name="prepare",
    group=plugin_group,
    description="Prepare venv for plugin",
    cwd=PROJECT_DIR,
    cmd_path=[
        os.path.join(PROJECT_DIR, "_cmd", "activate-venv.sh"),
        os.path.join(PROJECT_DIR, "_cmd", "prepare-venv.sh"),
    ],
)
runner.register(prepare_plugin)

###############################################################################
# ⚙️ build-plugin
###############################################################################

build_plugin = CmdTask(
    name="build",
    group=plugin_group,
    description="Build plugin",
    upstreams=[prepare_plugin],
    cwd=PROJECT_DIR,
    cmd_path=[
        os.path.join(PROJECT_DIR, "_cmd", "activate-venv.sh"),
        os.path.join(PROJECT_DIR, "_cmd", "build.sh"),
    ],
)
runner.register(build_plugin)

###############################################################################
# ⚙️ publish-plugin
###############################################################################

publish_plugin = CmdTask(
    name="publish",
    group=plugin_group,
    description="Publish plugin",
    inputs=[
        StrInput(
            name="plugin-repo",
            prompt="Pypi repository for plugin",
            description="Pypi repository for human readalbe zrb package name",
            default="pypi",
        )
    ],
    upstreams=[build_plugin],
    cwd=PROJECT_DIR,
    cmd_path=[
        os.path.join(PROJECT_DIR, "_cmd", "activate-venv.sh"),
        os.path.join(PROJECT_DIR, "_cmd", "publish.sh"),
    ],
)
runner.register(publish_plugin)

###############################################################################
# ⚙️ install-symlink
###############################################################################

install_plugin_symlink = CmdTask(
    name="install-symlink",
    group=plugin_group,
    description="Install plugin as symlink",
    upstreams=[build_plugin],
    cwd=PROJECT_DIR,
    cmd_path=[
        os.path.join(PROJECT_DIR, "_cmd", "activate-venv.sh"),
        os.path.join(PROJECT_DIR, "_cmd", "install-symlink.sh"),
    ],
)
runner.register(install_plugin_symlink)
