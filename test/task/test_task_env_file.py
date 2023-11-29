from zrb.task.task import Task
from zrb.task_env.env_file import EnvFile
import os


def test_task_with_env_file():
    def _run(*args, **kwargs) -> str:
        task: Task = kwargs.get('_task')
        env_map = task.get_env_map()
        return env_map.get('COLOR')
    env_file = os.path.join(
        os.path.dirname(__file__), 'test_task_env_file.env'
    )
    task = Task(
        name='env-file',
        env_files=[EnvFile(env_file=env_file)],
        run=_run,
        retry=0
    )
    function = task.to_function()
    result = function()
    assert result == 'blue'


def test_task_with_env_file_and_prefix():
    def _run(*args, **kwargs) -> str:
        task: Task = kwargs.get('_task')
        env_map = task.get_env_map()
        return env_map.get('COLOR')
    env_file = os.path.join(
        os.path.dirname(__file__), 'test_task_env_file.env'
    )
    task = Task(
        name='env-file-prefixed',
        env_files=[
            EnvFile(
                env_file=env_file, prefix='ZRB_TEST_TASK_WITH_ENV_AND_PREFIX'
            )
        ],
        run=_run,
        retry=0
    )
    function = task.to_function()
    if 'ZRB_TEST_TASK_WITH_ENV_AND_PREFIX_COLOR' in os.environ:
        del os.environ['ZRB_TEST_TASK_WITH_ENV_AND_PREFIX_COLOR']
    os.environ['ZRB_TEST_TASK_WITH_ENV_AND_PREFIX_COLOR'] = 'red'
    result = function()
    assert result == 'red'
    del os.environ['ZRB_TEST_TASK_WITH_ENV_AND_PREFIX_COLOR']
