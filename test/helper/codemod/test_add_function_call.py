from zrb.helper.codemod.add_function_call import add_function_call


def test_import_module():
    code = add_function_call(
        code='\n'.join([
            'def add(a, b):',
            '    return a + b'
        ]),
        function_name='add',
        parameters=['4', '5']
    )
    assert code == '\n'.join([
        'def add(a, b):',
        '    return a + b',
        'add(4, 5)'
    ])
