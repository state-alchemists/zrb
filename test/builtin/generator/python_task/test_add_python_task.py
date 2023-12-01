from zrb.builtin.generator.project.create import create_project
from zrb.builtin.generator.python_task.add import add_python_task
import os
import pathlib
import shutil


def test_add_python_task():
    # prepare path
    dir_path = pathlib.Path(__file__).parent.absolute()
    project_path = os.path.join(dir_path, 'app')
    # remove destination if exists
    if os.path.exists(project_path):
        shutil.rmtree(project_path)

    create_project_fn = create_project.to_function()
    create_project_fn(project_dir=project_path)

    automate_path = os.path.join(project_path, '_automate')

    # first attempt should success
    first_attempt_fn = add_python_task.to_function()
    first_attempt_fn(
        project_dir=project_path, task_name='pythonTask'
    )

    # cmd_task.py file should exists
    assert os.path.isfile(
        os.path.join(automate_path, 'python_task.py')
    )

    # cmd_task should be imported
    with open(os.path.join(project_path, 'zrb_init.py')) as f:
        content = f.read()
    assert 'assert python_task' in content
    assert 'import _automate.python_task as python_task' in content

    # second attempt should fail
    is_error = False
    try:
        second_attempt_fn = add_python_task.to_function()
        second_attempt_fn(
            project_dir=project_path, task_name='pythonTask'
        )
    except Exception:
        is_error = True
    assert is_error
