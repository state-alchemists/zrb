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

    # _automation should exists
    assert os.path.isfile(
        os.path.join(automate_path, 'simple_app', 'local.py')
    )
    assert os.path.isfile(
        os.path.join(automate_path, 'simple_app', 'container.py')
    )
    assert os.path.isfile(
        os.path.join(automate_path, 'simple_app', 'deployment.py')
    )

    # src should exists
    assert os.path.isfile(
        os.path.join(src_path, 'simple-app', 'docker-compose.yml')
    )

    # python_app should be imported
    expected_lines = [
        'assert _project',
        'assert simple_app_local',
        'assert simple_app_container',
        'assert simple_app_deployment',
        'import _automate._project as _project',
        'import _automate.simple_app.local as simple_app_local',
        'import _automate.simple_app.container as simple_app_container',
        'import _automate.simple_app.deployment as simple_app_deployment',
    ]
    with open(os.path.join(project_path, 'zrb_init.py')) as f:
        content = f.read()
        for line in expected_lines:
            assert line in content

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
