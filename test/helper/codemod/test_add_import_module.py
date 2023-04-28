from zrb.helper.codemod.add_import_module import add_import_module


def test_import_module():
    code = add_import_module(
        code='',
        module_path='my_package.my_module'
    )
    assert code == 'import my_package.my_module\n'


def test_import_module_relative():
    is_error = False
    try:
        add_import_module(
            code='',
            module_path='.my_package.my_module',
        )
    except Exception:
        is_error = True
    assert is_error


def test_import_module_with_alias():
    code = add_import_module(
        code='',
        module_path='my_package.my_module',
        alias='alias'

    )
    assert code == 'import my_package.my_module as alias\n'


def test_import_from_module():
    code = add_import_module(
        code='',
        module_path='my_package.my_module',
        resource='resource'
    )
    assert code == 'from my_package.my_module import resource\n'


def test_import_from_module_relative():
    code = add_import_module(
        code='',
        module_path='.my_package.my_module',
        resource='resource'
    )
    assert code == 'from .my_package.my_module import resource\n'


def test_import_from_module_with_alias():
    code = add_import_module(
        code='',
        module_path='my_package.my_module',
        resource='resource',
        alias='alias'
    )
    assert code == 'from my_package.my_module import resource as alias\n'


def test_import_from_module_with_alias_on_existing_code():
    code = add_import_module(
        code='from somewhere import something\n',
        module_path='my_package.my_module',
        resource='resource',
        alias='alias'
    )
    assert code == '\n'.join([
        'from somewhere import something',
        'from my_package.my_module import resource as alias'
    ]) + '\n'
