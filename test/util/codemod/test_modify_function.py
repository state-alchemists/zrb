import textwrap

from zrb.util.codemod.modify_function import (
    append_code_to_function,
    prepend_code_to_function,
    replace_function_code,
)

original_code = """
def existing_function(self):
    print("This is the existing method")
""".strip()

additional_code = """
print("This is new code inside the method")
""".strip()


def test_replace_function_code():
    new_code = replace_function_code(
        original_code, "existing_function", additional_code
    )
    assert (
        new_code
        == textwrap.dedent(
            """
        def existing_function(self):
            print("This is new code inside the method")
        """
        ).strip()
    )


def test_prepend_code_to_function():
    new_code = prepend_code_to_function(
        original_code, "existing_function", additional_code
    )
    assert (
        new_code
        == textwrap.dedent(
            """
        def existing_function(self):
            print("This is new code inside the method")
            print("This is the existing method")
        """
        ).strip()
    )


def test_append_code_to_function():
    new_code = append_code_to_function(
        original_code, "existing_function", additional_code
    )
    assert (
        new_code
        == textwrap.dedent(
            """
        def existing_function(self):
            print("This is the existing method")
            print("This is new code inside the method")
        """
        ).strip()
    )
