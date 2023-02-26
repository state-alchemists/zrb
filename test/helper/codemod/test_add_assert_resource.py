from zrb.helper.codemod.add_assert_resource import add_assert_resource


def test_import_module():
    code = add_assert_resource(
        code='a = True',
        resource='a'
    )
    assert code == '\n'.join([
        'a = True',
        'assert a'
    ])
