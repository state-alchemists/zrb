from zrb.builtin.project.create import create_project
from zrb.builtin.project.add.fastapp.app import add_fastapp_application
import os
import pathlib
import shutil


def test_add_fastapp_task():
    # prepare path
    dir_path = pathlib.Path(__file__).parent.absolute()
    project_path = os.path.join(dir_path, 'app')
    # remove destination if exists
    if os.path.exists(project_path):
        shutil.rmtree(project_path)

    create_project_fn = create_project.to_function()
    create_project_fn(project_dir=project_path)

    # first attempt should success
    first_attempt_fn = add_fastapp_application.to_function()
    first_attempt_fn(
        project_dir=project_path, app_name='fastapp', http_port=3000
    )

    with open(os.path.join(project_path, 'zrb_init.py')) as f:
        content = f.read()
    assert 'assert _automate_fastapp' in content
    assert 'import _automate.fastapp as _automate_fastapp' in content

    # inspect main.py content
    main_py_path = os.path.join(
        project_path, 'src', 'fastapp', 'src', 'main.py'
    )
    with open(main_py_path) as f:
        content = f.read()
    assert 'from integration.app.app import app' in content
    assert 'assert app' in content

    # second attempt should fail
    is_error = False
    try:
        second_attempt_fn = add_fastapp_application.to_function()
        second_attempt_fn(
            project_dir=project_path, app_name='fastapp', http_port=3000
        )
    except Exception:
        is_error = True
    assert is_error
