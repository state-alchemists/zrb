from zrb.builtin.project.create import create_task
from zrb.builtin.project.add.cmd_task.add import add_task
import os
import pathlib
import shutil


def test_task_create():
    # prepare path
    dir_path = pathlib.Path(__file__).parent.absolute()
    project_path = os.path.join(dir_path, 'app')
    # remove destination if exists
    if os.path.exists(project_path):
        shutil.rmtree(project_path)

    create_project = create_task.create_main_loop()
    create_project(project_dir=project_path)

    automate_path = os.path.join(project_path, '_automate')

    # first attempt should success
    first_attempt_loop = add_task.create_main_loop()
    result = first_attempt_loop(
        project_dir=project_path, task_name='cmdTask'
    )
    assert result

    # cmd_task.py file should exists
    assert os.path.isfile(
        os.path.join(automate_path, 'cmd_task.py')
    )

    # cmd_task should be imported
    with open(os.path.join(project_path, 'zrb_init.py')) as f:
        content = f.read()
        assert 'assert cmd_task' in content
        assert 'import _automate.cmd_task as cmd_task' in content

    # second attempt should fail
    is_error = False
    try:
        second_attempt_loop = add_task.create_main_loop()
        result = second_attempt_loop(
            project_dir=project_path, task_name='cmdTask'
        )
    except Exception:
        is_error = True
    assert is_error
