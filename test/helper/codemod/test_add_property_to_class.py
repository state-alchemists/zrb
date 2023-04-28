from zrb.helper.codemod.add_property_to_class import (
    add_property_to_class
)


def test_add_property_to_class():
    code = add_property_to_class(
        code='\n'.join([
            'class Cls():',
            '    existing_property: int',
            'class Something():',
            '    existing_property: int',
        ]),
        class_name='Something',
        property_name='some_property',
        property_type='int'
    )
    assert code == '\n'.join([
        'class Cls():',
        '    existing_property: int',
        'class Something():',
        '    existing_property: int',
        '    some_property: int',
    ])
