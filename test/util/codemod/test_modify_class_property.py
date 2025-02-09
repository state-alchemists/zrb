import textwrap

from zrb.util.codemod.modify_class_property import (
    append_property_to_class,
    prepend_property_to_class,
)

empty_class = """
class MyClass:
    '''Just a docstring'''
""".strip()

class_without_existing_properties = """
class MyClass:
    def do_something(self):
        pass
""".strip()

class_with_existing_properties = """
class MyClass:
    some_other_property = "default"
    def do_something(self):
        pass
""".strip()


def test_append_property_to_empty_class():
    new_code = append_property_to_class(
        empty_class, "MyClass", "new_property", "int", "100"
    )
    assert (
        new_code
        == textwrap.dedent(
            """
        class MyClass:
            '''Just a docstring'''
            new_property: int = 100
        """
        ).strip()
    )


def test_append_property_to_class_without_existing_properties():
    new_code = append_property_to_class(
        class_without_existing_properties, "MyClass", "new_property", "int", "100"
    )
    assert (
        new_code
        == textwrap.dedent(
            """
        class MyClass:
            new_property: int = 100
            def do_something(self):
                pass
        """
        ).strip()
    )


def test_append_property_to_class_with_existing_properties():
    new_code = append_property_to_class(
        class_with_existing_properties, "MyClass", "new_property", "int", "100"
    )
    assert (
        new_code
        == textwrap.dedent(
            """
        class MyClass:
            some_other_property = "default"
            new_property: int = 100
            def do_something(self):
                pass
        """
        ).strip()
    )


def test_prepend_property_to_class():
    new_code = prepend_property_to_class(
        class_with_existing_properties, "MyClass", "new_property", "int", "100"
    )
    assert (
        new_code
        == textwrap.dedent(
            """
        class MyClass:
            new_property: int = 100
            some_other_property = "default"
            def do_something(self):
                pass
        """
        ).strip()
    )
