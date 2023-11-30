from zrb.task.any_task import AnyTask
from zrb.task.task import Task
from zrb.task.cmd_task import CmdTask
from zrb.task_input.str_input import StrInput
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile

import os

CURRENT_DIR = os.path.dirname(__file__)


def test_task_copy():
    def _run(*args, **kwargs) -> str:
        name = kwargs.get('name')
        task: AnyTask = kwargs.get('_task')
        env_map = task.get_env_map()
        environment = env_map.get('ENVIRONMENT')
        host = env_map.get('HOST')
        return f'hello {name} on {environment}, host: {host}'
    task = Task(
        name='task',
        inputs=[
            StrInput(name='name', default='Nicholas Flamel')
        ],
        envs=[
            Env(name='ENVIRONMENT', default='dev')
        ],
        env_files=[
            EnvFile(env_file=os.path.join(CURRENT_DIR, 'env_file.env'))
        ],
        run=_run,
        retry=0
    )
    new_task: Task = task.copy()
    new_task.set_name('new-task')
    assert task.get_cmd_name() == 'task'
    assert new_task.get_cmd_name() == 'new-task'
    assert task.get_description() == 'task'
    assert new_task.get_description() == 'new-task'
    new_task.set_description('new description')
    assert task.get_cmd_name() == 'task'
    assert new_task.get_cmd_name() == 'new-task'
    assert task.get_description() == 'task'
    assert new_task.get_description() == 'new description'
    new_task.set_icon('🔥')
    assert new_task.get_icon() == '🔥'
    new_task.set_color('green')
    assert new_task.get_color() == 'green'
    new_task.set_retry(1)
    assert new_task._retry == 1
    new_task.add_input(StrInput(name='name', default='Dumbledore'))
    new_task.add_env(Env(name='ENVIRONMENT', default='prod'))
    new_task.add_env_file(
        EnvFile(env_file=os.path.join(CURRENT_DIR, 'new_env_file.env'))
    )
    function = new_task.to_function()
    result = function()
    assert result == 'hello Dumbledore on prod, host: stalchmst.com'


def test_cmd_task_copy():
    task = CmdTask(
        name='task',
        inputs=[
            StrInput(name='name', default='Nicholas Flamel')
        ],
        envs=[
            Env(name='ENVIRONMENT', default='dev')
        ],
        env_files=[
            EnvFile(env_file=os.path.join(CURRENT_DIR, 'env_file.env'))
        ],
        cwd=CURRENT_DIR,
        cmd='echo hello $_INPUT_NAME on $ENVIRONMENT, host: $HOST',
        retry=0
    )
    new_task: CmdTask = task.copy()
    new_task.set_name('new-task')
    assert task.get_cmd_name() == 'task'
    assert new_task.get_cmd_name() == 'new-task'
    assert task.get_description() == 'task'
    assert new_task.get_description() == 'new-task'
    new_task.set_description('new description')
    assert task.get_cmd_name() == 'task'
    assert new_task.get_cmd_name() == 'new-task'
    assert task.get_description() == 'task'
    assert new_task.get_description() == 'new description'
    new_task.set_icon('🔥')
    assert new_task.get_icon() == '🔥'
    new_task.set_color('green')
    assert new_task.get_color() == 'green'
    new_task.set_retry(1)
    assert new_task._retry == 1
    new_task.set_cwd(os.path.dirname(CURRENT_DIR))
    assert task._cwd == CURRENT_DIR
    assert new_task._cwd == os.path.dirname(CURRENT_DIR)
    new_task.add_input(StrInput(name='name', default='Dumbledore'))
    new_task.add_env(Env(name='ENVIRONMENT', default='prod'))
    new_task.add_env_file(
        EnvFile(env_file=os.path.join(CURRENT_DIR, 'new_env_file.env'))
    )
    function = new_task.to_function()
    result = function()
    assert result.output == 'hello Dumbledore on prod, host: stalchmst.com'
