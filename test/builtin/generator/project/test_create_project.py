from zrb.builtin.project.create import create_project
from zrb.config.config import version
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
    first_attempt_fn = create_project.to_function()
    is_error = False
    try:
        first_attempt_fn(project_dir=destination_path)
    except Exception:
        is_error = True
    assert not is_error

    # .git directory should exists
    assert os.path.isdir(os.path.join(destination_path, '.git'))
    # .gitignore file should exists
    assert os.path.isfile(os.path.join(destination_path, '.gitignore'))
    # zrb_init.py should exists
    assert os.path.isfile(os.path.join(destination_path, 'zrb_init.py'))

    with open(os.path.join(destination_path, 'README.md')) as readme_file:
        readme_lines = readme_file.readlines()
    assert readme_lines[0] == '# App\n'

    with open(
        os.path.join(destination_path, 'pyproject.toml')
    ) as pyproject_file:
        pyproject_lines = pyproject_file.readlines()
    assert f'zrb = ">={version}"\n' in pyproject_lines

    # second attempt should failed
    is_error = False
    try:
        second_attempt_fn = create_project.to_function()
        second_attempt_fn(project_dir=destination_path)
    except Exception:
        is_error = True
    assert is_error
