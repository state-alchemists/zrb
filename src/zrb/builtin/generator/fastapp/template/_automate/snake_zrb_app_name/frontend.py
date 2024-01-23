import os

from zrb import CmdTask, Env, EnvFile, PathChecker, runner
from zrb.builtin.group import project_group

from ._config import (
    APP_FRONTEND_BUILD_DIR,
    APP_FRONTEND_DIR,
    APP_TEMPLATE_ENV_FILE_NAME,
    CURRENT_DIR,
)

###############################################################################
# ⚙️ build-kebab-zrb-task-name-frontend
###############################################################################

build_snake_zrb_app_name_frontend = CmdTask(
    icon="🚤",
    name="build-kebab-zrb-app-name-frontend",
    description="Build frontend for human readable zrb app name",
    group=project_group,
    cwd=APP_FRONTEND_DIR,
    cmd_path=os.path.join(CURRENT_DIR, "cmd", "app-build-frontend.sh"),
    checkers=[
        PathChecker(
            name="check-kebab-zrb-app-name-frontend-build", path=APP_FRONTEND_BUILD_DIR
        )
    ],
    env_files=[
        EnvFile(path=APP_TEMPLATE_ENV_FILE_NAME, prefix="ZRB_ENV_PREFIX"),
    ],
    envs=[Env(name="WATCH", os_name="", default="1")],
)
runner.register(build_snake_zrb_app_name_frontend)

###############################################################################
# ⚙️ build-kebab-zrb-task-name-frontend-once
###############################################################################

build_snake_zrb_app_name_frontend_once = CmdTask(
    icon="🚤",
    name="build-kebab-zrb-app-name-frontend_once",
    description="Build frontend for human readable zrb app name",
    cwd=APP_FRONTEND_DIR,
    cmd_path=os.path.join(CURRENT_DIR, "cmd", "app-build-frontend.sh"),
    checkers=[
        PathChecker(
            name="check-kebab-zrb-app-name-frontend-build", path=APP_FRONTEND_BUILD_DIR
        )
    ],
    env_files=[
        EnvFile(path=APP_TEMPLATE_ENV_FILE_NAME, prefix="ZRB_ENV_PREFIX"),
    ],
    envs=[Env(name="WATCH", os_name="", default="0")],
)
