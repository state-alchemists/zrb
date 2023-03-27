from zrb import CmdTask, runner
from zrb.builtin._group import project_group
from ._common import APP_FRONTEND_DIR, CURRENT_DIR
import os

###############################################################################
# Task Definitions
###############################################################################

build_snake_app_name_frontend = CmdTask(
    icon='🚤',
    name='build-kebab-app-name-frontend',
    description='Build frontend for human readable app name',
    group=project_group,
    cwd=APP_FRONTEND_DIR,
    cmd_path=os.path.join(CURRENT_DIR, 'cmd', 'build-frontend.sh'),
)
runner.register(build_snake_app_name_frontend)
