from zrb.builtin.generator.project.create import create_project
from zrb.builtin.generator.fastapp.add import add_fastapp
from zrb.builtin.generator.fastapp_module.add import add_fastapp_module
import os
import pathlib
import shutil


def test_add_fastapp_module():
    # prepare path
    dir_path = pathlib.Path(__file__).parent.absolute()
    project_path = os.path.join(dir_path, 'app')
    # remove destination if exists
    if os.path.exists(project_path):
        shutil.rmtree(project_path)

    create_project_fn = create_project.to_function()
    create_project_fn(project_dir=project_path)
    add_fastapp_fn = add_fastapp.to_function()
    add_fastapp_fn(
        project_dir=project_path, app_name='fastapp', http_port=3000
    )

    # first attempt should success
    first_attempt_fn = add_fastapp_module.to_function()
    first_attempt_fn(
        project_dir=project_path, app_name='fastapp', module_name='library'
    )

    # inspect main.py content
    main_py_path = os.path.join(
        project_path, 'src', 'fastapp', 'src', 'main.py'
    )
    with open(main_py_path) as f:
        content = f.read()
    assert 'from component.app import app' in content
    assert 'from module.library.register_module import register_library' in content  # noqa
    assert 'register_library()' in content

    # second attempt should fail
    is_error = False
    try:
        second_attempt_fn = add_fastapp_module.to_function()
        second_attempt_fn(
            project_dir=project_path, app_name='fastapp', module_name='library'
        )
    except Exception:
        is_error = True
    assert is_error
