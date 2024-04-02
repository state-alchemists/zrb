from zrb.builtin.project.create import create_project
from zrb.builtin.project.add.fastapp.app import add_fastapp_application
from zrb.builtin.project.add.fastapp.module import add_fastapp_module
from zrb.builtin.project.add.fastapp.crud import add_fastapp_crud
import os
import pathlib
import shutil


def test_add_fastapp_crud():
    # prepare path
    dir_path = pathlib.Path(__file__).parent.absolute()
    project_path = os.path.join(dir_path, 'app')
    # remove destination if exists
    if os.path.exists(project_path):
        shutil.rmtree(project_path)

    create_project_fn = create_project.to_function()
    create_project_fn(project_dir=project_path)
    add_fastapp_fn = add_fastapp_application.to_function()
    add_fastapp_fn(
        project_dir=project_path, app_name='fastapp', http_port=3000
    )
    add_fastapp_module_fn = add_fastapp_module.to_function()
    add_fastapp_module_fn(
        project_dir=project_path, app_name='fastapp', module_name='library'
    )

    # first attempt should success
    first_attempt_fn = add_fastapp_crud.to_function()
    first_attempt_fn(
        project_dir=project_path,
        app_name='fastapp',
        module_name='library',
        entity_name='book',
        plural_entity_name='books',
        column_name='code'
    )

    assert os.path.isdir(os.path.join(
        project_path, 'src', 'fastapp', 'src', 'module', 'library', 'entity', 'book'  # noqa
    ))

    # second attempt should fail
    is_error = False
    try:
        second_attempt_fn = add_fastapp_crud.to_function()
        second_attempt_fn(
            project_dir=project_path,
            app_name='fastapp',
            module_name='library',
            entity_name='book',
            plural_entity_name='books',
            column_name='code'
        )
    except Exception:
        is_error = True
    assert is_error
