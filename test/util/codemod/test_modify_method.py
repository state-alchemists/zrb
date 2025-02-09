import textwrap

from zrb.util.codemod.modify_method import (
    append_code_to_method,
    prepend_code_to_method,
    replace_method_code,
)

original_code = """
class MyClass:
    def existing_method(self):
        print("This is the existing method")
""".strip()

additional_code = """
print("This is new code inside the method")
""".strip()


def test_replace_method_code():
    new_code = replace_method_code(
        original_code, "MyClass", "existing_method", additional_code
    )
    assert (
        new_code
        == textwrap.dedent(
            """
        class MyClass:
            def existing_method(self):
                print("This is new code inside the method")
        """
        ).strip()
    )


def test_prepend_code_to_method():
    new_code = prepend_code_to_method(
        original_code, "MyClass", "existing_method", additional_code
    )
    assert (
        new_code
        == textwrap.dedent(
            """
        class MyClass:
            def existing_method(self):
                print("This is new code inside the method")
                print("This is the existing method")
        """
        ).strip()
    )


def test_append_code_to_method():
    new_code = append_code_to_method(
        original_code, "MyClass", "existing_method", additional_code
    )
    assert (
        new_code
        == textwrap.dedent(
            """
        class MyClass:
            def existing_method(self):
                print("This is the existing method")
                print("This is new code inside the method")
        """
        ).strip()
    )
