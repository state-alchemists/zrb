from zrb.task.resource_maker import ResourceMaker
import os
import pathlib
import shutil


def test_resource_maker():
    # prepare path
    dir_path = pathlib.Path(__file__).parent.absolute()
    template_path = os.path.join(dir_path, 'template')
    destination_path = os.path.join(dir_path, 'app')
    # remove destination if exists
    if os.path.exists(destination_path):
        shutil.rmtree(destination_path)

    # initiate code_maker
    code_maker = ResourceMaker(
        name='create-app',
        template_path=template_path,
        destination_path=destination_path,
        excludes=['*/excluded'],
        replacements={
            'app_name': 'my_app',
            '3000': '8080'
        },
        scaffold_locks=[destination_path]
    )

    # first attempt should succeed
    first_attempt_loop = code_maker.create_main_loop()
    result = first_attempt_loop()
    assert result
    # excluded should not exists
    assert not os.path.exists(os.path.join(
        destination_path, 'excluded'
    ))

    # config_my_app.py should exists and contain the right data
    assert read_file(
        os.path.join(destination_path, 'src', 'config_my_app.py')
    ) == '\n'.join([
        'port = 8080',
        ''
    ])

    # my_app.py should exists and contain the right data
    assert read_file(
        os.path.join(destination_path, 'src', 'my_app.py')
    ) == '\n'.join([
        'from config_my_app import port',
        '',
        '',
        'def start():',
        "    print(f'starting my_app on port {port}')",
        '    return True',
        ''
    ])

    # second attempt should failed
    is_error = False
    try:
        second_attempt_loop = code_maker.create_main_loop()
        result = second_attempt_loop()
    except Exception:
        is_error = True
    assert is_error


def read_file(file_name: str) -> str:
    with open(file_name) as f:
        return f.read()
