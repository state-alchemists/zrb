from zrb.util.codemod.append_key_to_dict import append_key_to_dict

original_code = """
my_dict = {"existing_key": "existing_value"}
"""

expected_new_code = """
my_dict = {"existing_key": "existing_value", "new_key": "new_value"}
"""


def test_append_code_to_method():
    new_code = append_key_to_dict(
        original_code.strip(), "my_dict", "new_key", "new_value"
    )
    assert new_code == expected_new_code.strip()
