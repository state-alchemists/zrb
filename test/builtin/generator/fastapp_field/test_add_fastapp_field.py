from zrb.builtin.generator.project.create import create_project
from zrb.builtin.generator.fastapp.add import add_fastapp
from zrb.builtin.generator.fastapp_module.add import add_fastapp_module
from zrb.builtin.generator.fastapp_crud.add import add_fastapp_crud
from zrb.builtin.generator.fastapp_field.add import add_fastapp_field
import os
import pathlib
import shutil


def test_add_fastapp_field():
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
    add_fastapp_module_fn = add_fastapp_module.to_function()
    add_fastapp_module_fn(
        project_dir=project_path, app_name='fastapp', module_name='library'
    )
    add_fastapp_crud_fn = add_fastapp_crud.to_function()
    add_fastapp_crud_fn(
        project_dir=project_path,
        app_name='fastapp',
        module_name='library',
        entity_name='book',
        plural_entity_name='books',
        column_name='code'
    )

    # first attempt should success
    first_attempt_fn = add_fastapp_field.to_function()
    first_attempt_fn(
        project_dir=project_path,
        app_name='fastapp',
        module_name='library',
        entity_name='book',
        column_name='title',
        column_type='str'
    )

    book_schema_py = os.path.join(
        project_path, 'src', 'fastapp', 'src', 'module', 'library', 'schema', 'book.py'  # noqa
    )

    with open(book_schema_py, 'r') as file:
        content = file.read()
        assert 'title' in content
