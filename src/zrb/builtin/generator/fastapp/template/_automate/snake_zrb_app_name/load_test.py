from zrb import CmdTask, EnvFile, BoolInput, StrInput, IntInput, runner
from zrb.builtin.group import project_group
from ._common import CURRENT_DIR, RESOURCE_DIR
import os

###############################################################################
# Constants
###############################################################################

LOAD_TEST_DIR = os.path.join(RESOURCE_DIR, 'loadtest')
LOAD_TEST_TEMPLATE_ENV_FILE_NAME = os.path.join(RESOURCE_DIR, 'template.env')

###############################################################################
# Input Definitions
###############################################################################

headless_input = BoolInput(
    name='kebab-zrb-app-name-load-test-headless',
    default=True,
    description='Load test UI headless',
    prompt='Load test UI headless (if True, there will be no UI)',
)

web_port_input = IntInput(
    name='kebab-zrb-app-name-load-test-port',
    default=8089,
    description='Load test UI web port',
    prompt='Load test UI web port (Only works if headless is False)',
)

users_input = IntInput(
    name='kebab-zrb-app-name-load-test-users',
    default=200,
    description='Load test users',
    prompt='Load test users',
)

spawn_rate_input = IntInput(
    name='kebab-zrb-app-name-load-test-spawn-rate',
    default=10,
    description='Load test spawn rate',
    prompt='Load test spawn rate',
)

url_input = StrInput(
    name='kebab-zrb-app-name-load-test-url',
    default='http://localhost:zrbAppHttpPort',
    description='Load test url',
    prompt='Load test url',
)

###############################################################################
# Env file Definitions
###############################################################################

load_test_env_file = EnvFile(
    env_file=LOAD_TEST_TEMPLATE_ENV_FILE_NAME,
    prefix='LOAD_TEST_ZRB_ENV_PREFIX'
)

###############################################################################
# Task Definitions
###############################################################################

prepare_snake_zrb_app_name_load_test = CmdTask(
    icon='🚤',
    name='prepare-kebab-zrb-app-name-load-test',
    description='Prepare load test for human readable zrb app name',
    group=project_group,
    cwd=LOAD_TEST_DIR,
    cmd_path=[
        os.path.join(CURRENT_DIR, 'cmd', 'activate-venv.sh'),
        os.path.join(CURRENT_DIR, 'cmd', 'app-prepare-load-test.sh'),
    ]
)
runner.register(prepare_snake_zrb_app_name_load_test)

load_test_snake_zrb_app_name_load_test = CmdTask(
    icon='🧪',
    name='load-test-kebab-zrb-app-name',
    description='Load test human readable zrb app name',
    group=project_group,
    upstreams=[prepare_snake_zrb_app_name_load_test],
    inputs=[
        headless_input,
        web_port_input,
        users_input,
        spawn_rate_input,
        url_input,
    ],
    cwd=LOAD_TEST_DIR,
    env_files=[load_test_env_file],
    cmd_path=[
        os.path.join(CURRENT_DIR, 'cmd', 'activate-venv.sh'),
        os.path.join(CURRENT_DIR, 'cmd', 'app-load-test.sh'),
    ]
)
runner.register(load_test_snake_zrb_app_name_load_test)
