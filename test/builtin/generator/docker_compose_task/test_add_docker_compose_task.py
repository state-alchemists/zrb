from zrb.builtin.generator.project.create import create_project
from zrb.builtin.generator.docker_compose_task.add import (
    add_docker_compose_task
)
import os
import pathlib
import shutil


def test_add_docker_compose_task():
    # prepare path
    dir_path = pathlib.Path(__file__).parent.absolute()
    project_path = os.path.join(dir_path, 'app')
    # remove destination if exists
    if os.path.exists(project_path):
        shutil.rmtree(project_path)

    create_project_loop = create_project.create_main_loop()
    create_project_loop(project_dir=project_path)

    automate_path = os.path.join(project_path, '_automate')
    src_path = os.path.join(project_path, 'src')

    # first attempt should success
    first_attempt_loop = add_docker_compose_task.create_main_loop()
    first_attempt_loop(
        project_dir=project_path, task_name='composeTask'
    )

    # compose_task.py file should exists
    assert os.path.isfile(
        os.path.join(automate_path, 'compose_task.py')
    )
    assert os.path.isfile(
        os.path.join(src_path, 'compose-task', 'docker-compose.yml')
    )

    # compose_task should be imported
    with open(os.path.join(project_path, 'zrb_init.py')) as f:
        content = f.read()
        assert 'assert compose_task' in content
        assert 'import _automate.compose_task as compose_task' in content

    # second attempt should fail
    is_error = False
    try:
        second_attempt_loop = add_docker_compose_task.create_main_loop()
        second_attempt_loop(
            project_dir=project_path, task_name='composeTask'
        )
    except Exception:
        is_error = True
    assert is_error
