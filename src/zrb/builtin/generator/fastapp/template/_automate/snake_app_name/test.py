from zrb import CmdTask, StrInput, Env, EnvFile, runner
from zrb.builtin._group import project_group
from ._common import (
    CURRENT_DIR, RESOURCE_DIR, APP_TEMPLATE_ENV_FILE_NAME,
)
from .frontend import build_snake_app_name_frontend_once
from .local import prepare_snake_app_name_backend
import os

app_env_file = EnvFile(
    env_file=APP_TEMPLATE_ENV_FILE_NAME, prefix='TEST_ENV_PREFIX'
)

###############################################################################
# Task Definitions
###############################################################################

test_snake_app_name = CmdTask(
    icon='🚤',
    name='test-kebab-app-name',
    inputs=[
        StrInput(
            name='kebab-app-name-test',
            description='Specific test case (i.e., test/file.py::test_name)',
            prompt='Test (i.e., test/file.py::test_name)',
            default=''
        )
    ],
    upstreams=[
        build_snake_app_name_frontend_once,
        prepare_snake_app_name_backend,
    ],
    group=project_group,
    cwd=RESOURCE_DIR,
    env_files=[app_env_file],
    envs=[
        Env(
            name='APP_BROKER_TYPE',
            os_name='TEST_APP_BROKER_TYPE',
            default='mock'
        ),
        Env(
            name='APP_DB_CONNECTION',
            os_name='TEST_APP_DB_CONNECTION',
            default='sqlite:///'
        )
    ],
    cmd_path=os.path.join(CURRENT_DIR, 'cmd', 'test.sh'),
)
runner.register(test_snake_app_name)
