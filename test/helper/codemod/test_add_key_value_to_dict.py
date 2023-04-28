from zrb.helper.codemod.add_key_value_to_dict import (
    add_key_value_to_dict
)


def test_add_key_value_to_dict():
    code = add_key_value_to_dict(
        code='\n'.join([
            'person = {"name": "Bob", "age": 5}',
            'alchemist = {"name": "Eldric", "age": 15}',
        ]),
        dict_name='alchemist',
        key='"job"',
        value='"alchemist"'
    )
    assert code == '\n'.join([
        'person = {"name": "Bob", "age": 5}',
        'alchemist = {"name": "Eldric", "age": 15, "job": "alchemist"}',
    ])
