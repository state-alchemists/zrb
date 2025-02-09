import textwrap

from zrb.util.codemod.modify_class import (
    append_code_to_class,
    prepend_code_to_class,
    replace_class_code,
)

original_code = """
class OtherClass:
    def __init__(self):
        pass
def MyClass(x):
    pass
class MyClass:
    def __init__(self):
        self.value = 42
""".strip()

additional_code = """
def new_method(self):
    print("This is a new method")
""".strip()


def test_replace_class_code():
    new_code = replace_class_code(original_code, "MyClass", additional_code)
    assert (
        new_code
        == textwrap.dedent(
            """
        class OtherClass:
            def __init__(self):
                pass
        def MyClass(x):
            pass
        class MyClass:
            def new_method(self):
                print("This is a new method")
        """
        ).strip()
    )


def test_prepend_code_to_class():
    new_code = prepend_code_to_class(original_code, "MyClass", additional_code)
    assert (
        new_code
        == textwrap.dedent(
            """
        class OtherClass:
            def __init__(self):
                pass
        def MyClass(x):
            pass
        class MyClass:
            def new_method(self):
                print("This is a new method")
            def __init__(self):
                self.value = 42
        """
        ).strip()
    )


def test_append_code_to_class():
    new_code = append_code_to_class(original_code, "MyClass", additional_code)
    assert (
        new_code
        == textwrap.dedent(
            """
        class OtherClass:
            def __init__(self):
                pass
        def MyClass(x):
            pass
        class MyClass:
            def __init__(self):
                self.value = 42
            def new_method(self):
                print("This is a new method")
        """
        ).strip()
    )
