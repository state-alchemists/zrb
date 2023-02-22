from zrb.builtin.project.project_create_task import project_create_task
from zrb.builtin.task.task_create_task import task_create_task
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

    create_project = project_create_task.create_main_loop()
    create_project(project_dir=project_path)

    destination_path = os.path.join(project_path, 'transmutateGold')

    # first attempt should success
    first_attempt_loop = task_create_task.create_main_loop()
    result = first_attempt_loop(task_dir=destination_path)
    assert result

    # transmutation directory should exists
    assert os.path.isdir(os.path.join(destination_path))
    # transmutation.py file should exists
    assert os.path.isfile(
        os.path.join(destination_path, 'transmutate_gold.py')
    )

    # second attempt should success
    is_error = False
    try:
        second_attempt_loop = task_create_task.create_main_loop()
        result = second_attempt_loop(task_dir=destination_path)
    except Exception:
        is_error = True
    assert is_error
