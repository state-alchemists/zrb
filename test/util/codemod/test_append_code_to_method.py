from zrb.util.codemod.modify_method import append_code_to_method

original_code = """
class MyClass:
    def existing_method(self):
        print("This is the existing method")
"""

additional_code = """
print("This is new code inside the method")
"""

expected_new_code = """
class MyClass:
    def existing_method(self):
        print("This is the existing method")
        print("This is new code inside the method")
"""


def test_append_code_to_method():
    new_code = append_code_to_method(
        original_code.strip(), "MyClass", "existing_method", additional_code.strip()
    )
    assert new_code == expected_new_code.strip()
