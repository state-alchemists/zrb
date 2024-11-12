from zrb.util.codemod.add_property_to_class import add_property_to_class

original_code = """
class MyClass:
    some_other_property = "default"
"""

expected_new_code = """
class MyClass:
    new_property: int = 100
    some_other_property = "default"
"""


def test_add_property_to_class():
    new_code = add_property_to_class(
        original_code.strip(), "MyClass", "new_property", "int", "100"
    )
    assert new_code == expected_new_code.strip()
