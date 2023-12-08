from zrb import CmdTask, StrInput, Env, EnvFile, runner, python_task
from zrb.builtin.group import project_group
from ._common import CURRENT_DIR, RESOURCE_DIR, APP_TEMPLATE_ENV_FILE_NAME
from .frontend import build_snake_zrb_app_name_frontend_once
from .local import prepare_snake_zrb_app_name_backend
import os

###############################################################################
# Env file Definitions
###############################################################################

app_env_file = EnvFile(
    path=APP_TEMPLATE_ENV_FILE_NAME, prefix='TEST_ZRB_ENV_PREFIX'
)

###############################################################################
# Task Definitions
###############################################################################


@python_task(
    icon='🧪',
    name='remove-kebab-zrb-app-name-test-db',
    group=project_group,
    runner=runner
)
def remove_snake_zrb_app_name_test_db(*args, **kwargs):
    test_db_file_path = os.path.join(RESOURCE_DIR, 'test.db')
    if os.path.isfile(test_db_file_path):
        os.remove(test_db_file_path)


test_snake_zrb_app_name = CmdTask(
    icon='🚤',
    name='test-kebab-zrb-app-name',
    group=project_group,
    inputs=[
        StrInput(
            name='kebab-zrb-app-name-test',
            description='Specific test case (i.e., test/file.py::test_name)',
            prompt='Test (i.e., test/file.py::test_name)',
            default=''
        )
    ],
    upstreams=[
        build_snake_zrb_app_name_frontend_once,
        prepare_snake_zrb_app_name_backend,
        remove_snake_zrb_app_name_test_db,
    ],
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
            default='sqlite:///test.db'
        ),
        Env(
            name='APP_AUTH_ADMIN_ACTIVE',
            os_name='',
            default='true'
        ),
        Env(
            name='APP',
            os_name='APP_ENABLE_OTEL',
            default='false'
        ),
    ],
    cmd_path=os.path.join(CURRENT_DIR, 'cmd', 'app-test.sh'),
    retry=0
)
runner.register(test_snake_zrb_app_name)
