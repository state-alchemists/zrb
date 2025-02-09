import textwrap

from zrb.util.codemod.modify_dict import append_key_to_dict, prepend_key_to_dict

original_code = """
my_dict = {"existing_key": "existing_value"}
""".strip()


def test_prepend_key_to_dict():
    new_code = prepend_key_to_dict(original_code, "my_dict", "new_key", "new_value")
    assert (
        new_code
        == textwrap.dedent(
            """
        my_dict = {"new_key": "new_value", "existing_key": "existing_value"}
        """
        ).strip()
    )


def test_append_key_to_dict():
    new_code = append_key_to_dict(original_code, "my_dict", "new_key", "new_value")
    assert (
        new_code
        == textwrap.dedent(
            """
        my_dict = {"existing_key": "existing_value", "new_key": "new_value"}
        """
        ).strip()
    )
