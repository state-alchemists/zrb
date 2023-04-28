from zrb.helper.codemod.add_argument_to_function_call import (
    add_argument_to_function_call
)


def test_add_argument_to_function():
    code = add_argument_to_function_call(
        code='\n'.join([
            'def fn(a, b):',
            '    pass',
            'def add(a, b, c):',
            '    pass',
            'x = fn(1, 2)',
            'y = add(1, 2)',
        ]),
        function_name='add',
        argument_name='c',
    )
    assert code == '\n'.join([
        'def fn(a, b):',
        '    pass',
        'def add(a, b, c):',
        '    pass',
        'x = fn(1, 2)',
        'y = add(1, 2, c)',
    ])
