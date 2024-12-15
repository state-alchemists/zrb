from zrb.util.codemod.prepend_parent_to_class import prepend_parent_class

original_code = """
class MyClass(OriginalParent):
    pass
"""

expected_new_code = """
class MyClass(NewParent, OriginalParent):
    pass
"""


def test_prepend_code_to_method():
    new_code = prepend_parent_class(original_code.strip(), "MyClass", "NewParent")
    assert new_code == expected_new_code.strip()
