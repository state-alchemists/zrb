from zrb import (
    DockerComposeTask, HTTPChecker, Env, runner
)
import os

current_dir = os.path.dirname(__file__)
resource_dir = os.path.abspath(os.path.join(
    current_dir, '..', 'src', 'kebab-task-name')
)


snake_task_name = DockerComposeTask(
    name='kebab-task-name',
    description='human readable task name',
    cwd=resource_dir,
    compose_cmd='composeCommand',
    compose_env_prefix='ENV_PREFIX',
    envs=[
        Env(name='MESSAGE', os_name='ENV_PREFIX_MESSAGE', default='Salve Mane'),
        Env(name='PORT', os_name='ENV_PREFIX_PORT', default='3000'),
    ],
    checkers=[
        HTTPChecker(port='{{env.PORT}}')
    ]
)
runner.register(snake_task_name)
