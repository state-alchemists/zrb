from zrb.helper.codemod.add_argument_to_function import (
    add_argument_to_function
)


def test_add_argument_to_function():
    code = add_argument_to_function(
        code='\n'.join([
            'def fn(a, b):',
            '    pass',
            'def add(a, b):',
            '    pass',
        ]),
        function_name='add',
        argument_name='c',
        argument_type='int'
    )
    assert code == '\n'.join([
        'def fn(a, b):',
        '    pass',
        'def add(a, b, c: int):',
        '    pass',
    ])
