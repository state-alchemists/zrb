from zrb.builtin.generator.project.create import create_project
from zrb.builtin.generator.simple_python_app.add import (
    add_simple_python_app
)
import os
import pathlib
import shutil


def test_add_simple_python_app():
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
    first_attempt_loop = add_simple_python_app.create_main_loop()
    first_attempt_loop(
        project_dir=project_path, app_name='simpleApp'
    )

    # simple_app.py file should exists
    assert os.path.isfile(
        os.path.join(automate_path, 'simple_app.py')
    )
    assert os.path.isfile(
        os.path.join(src_path, 'simple-app', 'docker-compose.yml')
    )

    # python_app should be imported
    with open(os.path.join(project_path, 'zrb_init.py')) as f:
        content = f.read()
        assert 'assert simple_app' in content
        assert 'import _automate.simple_app as simple_app' in content

    # second attempt should fail
    is_error = False
    try:
        second_attempt_loop = add_simple_python_app.create_main_loop()
        second_attempt_loop(
            project_dir=project_path, app_name='simpleApp'
        )
    except Exception:
        is_error = True
    assert is_error
