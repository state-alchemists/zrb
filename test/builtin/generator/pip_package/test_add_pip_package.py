from zrb.builtin.generator.project.create import create_project
from zrb.builtin.generator.pip_package.add import (
    add_pip_package
)
import os
import pathlib
import shutil


def test_add_pip_package():
    # prepare path
    dir_path = pathlib.Path(__file__).parent.absolute()
    project_path = os.path.join(dir_path, 'app')
    # remove destination if exists
    if os.path.exists(project_path):
        shutil.rmtree(project_path)

    create_project_loop = create_project.to_function()
    create_project_loop(project_dir=project_path)

    automate_path = os.path.join(project_path, '_automate')
    src_path = os.path.join(project_path, 'src')

    # first attempt should success
    first_attempt_loop = add_pip_package.to_function()
    first_attempt_loop(
        project_dir=project_path, package_name='pip_package'
    )

    # compose_task.py file should exists
    assert os.path.isfile(
        os.path.join(automate_path, 'pip_package', 'local.py')
    )
    assert os.path.isfile(
        os.path.join(src_path, 'pip-package', 'pyproject.toml')
    )

    # compose_task should be imported
    with open(os.path.join(project_path, 'zrb_init.py')) as f:
        content = f.read()
    assert 'assert pip_package_local' in content
    assert 'import _automate.pip_package.local as pip_package_local' in content

    # second attempt should fail
    is_error = False
    try:
        second_attempt_loop = add_pip_package.to_function()
        second_attempt_loop(
            project_dir=project_path, package_name='pip_package'
        )
    except Exception:
        is_error = True
    assert is_error
