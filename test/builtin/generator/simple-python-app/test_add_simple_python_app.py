from zrb.builtin.project.create import create_project
from zrb.builtin.project.add.app.python import add_python_app
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

    create_project_fn = create_project.to_function()
    create_project_fn(project_dir=project_path)

    src_path = os.path.join(project_path, 'src')

    # first attempt should success
    first_attempt_fn = add_python_app.to_function()
    first_attempt_fn(
        project_dir=project_path, app_name='simpleApp'
    )

    # src should exists
    assert os.path.isfile(
        os.path.join(src_path, 'simple-app', 'docker-compose.yml')
    )

    # python_app should be imported
    with open(os.path.join(project_path, 'zrb_init.py')) as f:
        content = f.read()
    assert 'assert _automate_simple_app' in content
    assert 'import _automate.simple_app as _automate_simple_app' in content

    # second attempt should fail
    is_error = False
    try:
        second_attempt_fn = add_python_app.to_function()
        second_attempt_fn(
            project_dir=project_path, app_name='simpleApp'
        )
    except Exception:
        is_error = True
    assert is_error
