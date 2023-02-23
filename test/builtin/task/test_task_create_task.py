from zrb.builtin.project.create import create_task
from zrb.builtin.project.add.task.create import create_cmd_task
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

    destination_path = os.path.join(project_path, '_automate')

    # first attempt should success
    first_attempt_loop = create_cmd_task.create_main_loop()
    result = first_attempt_loop(task_dir=destination_path)
    assert result

    # transmutate_gold.py file should exists
    assert os.path.isfile(
        os.path.join(destination_path, 'transmutate_gold.py')
    )

    # second attempt should success
    is_error = False
    try:
        second_attempt_loop = create_cmd_task.create_main_loop()
        result = second_attempt_loop(task_dir=destination_path)
    except Exception:
        is_error = True
    assert is_error
