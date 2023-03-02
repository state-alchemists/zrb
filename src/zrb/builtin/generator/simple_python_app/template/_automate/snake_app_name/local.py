from zrb import (
    CmdTask, HTTPChecker, Env, runner
)
from zrb.builtin._group import project_group
import os

current_dir = os.path.dirname(__file__)
resource_dir = os.path.abspath(os.path.join(
    current_dir, '..', '..', 'src', 'kebab-app-name'
))


start_snake_app_name = CmdTask(
    name='start-kebab-app-name',
    description='Start human readable app name',
    group=project_group,
    cwd=os.path.join(resource_dir, 'src'),
    envs=[
        Env(
            name='MESSAGE',
            os_name='ENV_PREFIX_MESSAGE',
            default='Salve Mane'
        ),
        Env(
            name='PORT',
            os_name='ENV_PREFIX_HOST_PORT',
            default='httpPort'
        )
    ],
    cmd=[
        'if [ ! -d venv ]',
        'then',
        '  python -m venv venv',
        'fi',
        'pip install -r requirements.txt',
        'python main.py'
    ],
    checkers=[
        HTTPChecker(port='{{env.PORT}}')
    ]
)
runner.register(start_snake_app_name)
