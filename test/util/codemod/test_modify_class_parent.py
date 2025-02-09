import textwrap

from zrb.util.codemod.modify_class_parent import (
    append_parent_class,
    prepend_parent_class,
    replace_parent_class,
)

original_code = """
class MyClass(OriginalParent):
    pass
""".strip()


def test_replace_parent_class():
    new_code = replace_parent_class(original_code, "MyClass", "NewParent")
    assert (
        new_code
        == textwrap.dedent(
            """
        class MyClass(NewParent):
            pass
        """
        ).strip()
    )


def test_append_parent_class():
    new_code = append_parent_class(original_code, "MyClass", "NewParent")
    assert (
        new_code
        == textwrap.dedent(
            """
        class MyClass(OriginalParent, NewParent):
            pass
        """
        ).strip()
    )


def test_prepend_parent_class():
    new_code = prepend_parent_class(original_code, "MyClass", "NewParent")
    assert (
        new_code
        == textwrap.dedent(
            """
        class MyClass(NewParent, OriginalParent):
            pass
        """
        ).strip()
    )
