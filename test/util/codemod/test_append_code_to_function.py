from zrb.util.codemod.append_code_to_function import append_code_to_function

original_code = """
def existing_function(self):
    print("This is the existing method")
"""

additional_code = """
print("This is new code inside the method")
"""

expected_new_code = """
def existing_function(self):
    print("This is the existing method")
    print("This is new code inside the method")
"""


def test_append_code_to_function():
    new_code = append_code_to_function(
        original_code.strip(), "existing_function", additional_code.strip()
    )
    assert new_code == expected_new_code.strip()
