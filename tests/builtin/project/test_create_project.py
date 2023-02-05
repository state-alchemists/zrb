from zrb.builtin.project.create_project import create_project
import os
import pathlib
import shutil


def test_create_project():
    # prepare path
    dir_path = pathlib.Path(__file__).parent.absolute()
    destination_path = os.path.join(dir_path, 'app')
    # remove destination if exists
    if os.path.exists(destination_path):
        shutil.rmtree(destination_path)

    # first attempt should success
    first_attempt_loop = create_project.create_main_loop()
    result = first_attempt_loop(project_dir=destination_path)
    assert result

    # .git directory should exists
    assert os.path.isdir(os.path.join(destination_path, '.git'))
    # .gitignore file should exists
    assert os.path.isfile(os.path.join(destination_path, '.gitignore'))
    # zrb_init.py should exists
    assert os.path.isfile(os.path.join(destination_path, 'zrb_init.py'))

    # second attempt should success
    is_error = False
    try:
        second_attempt_loop = create_project.create_main_loop()
        result = second_attempt_loop(project_dir=destination_path)
    except Exception:
        is_error = True
    assert is_error
