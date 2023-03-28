from typing import Any
from zrb import CmdTask, Task, python_task, runner
from zrb.builtin._group import project_group
from ._common import APP_FRONTEND_DIR, APP_FRONTEND_BUILD_DIR, CURRENT_DIR
import asyncio
import os

###############################################################################
# Task Definitions
###############################################################################


@python_task(
    name='check-kebab-app-name-frontend-build',
    retry=0,
)
async def check_frontend_build(*args: str, **kwargs: Any):
    while not os.path.isdir(APP_FRONTEND_BUILD_DIR):
        await asyncio.sleep(0.1)
    task: Task = kwargs.get('_task')
    task.print_out(f'Frontend built: {APP_FRONTEND_BUILD_DIR}')


build_snake_app_name_frontend = CmdTask(
    icon='🚤',
    name='build-kebab-app-name-frontend',
    description='Build frontend for human readable app name',
    group=project_group,
    cwd=APP_FRONTEND_DIR,
    cmd_path=os.path.join(CURRENT_DIR, 'cmd', 'build-frontend.sh'),
    checkers=[check_frontend_build]
)
runner.register(build_snake_app_name_frontend)
