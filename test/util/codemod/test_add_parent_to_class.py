from zrb.util.codemod.add_parent_to_class import add_parent_to_class

original_code = """
class MyClass(OriginalParent):
    pass
"""

expected_new_code = """
class MyClass(NewParent, OriginalParent):
    pass
"""


def test_add_code_to_method():
    new_code = add_parent_to_class(original_code.strip(), "MyClass", "NewParent")
    assert new_code == expected_new_code.strip()
