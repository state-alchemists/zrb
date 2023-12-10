from zrb.helper.docstring import get_markdown_from_docstring


class SampleClass:
    """
    This is a sample class for testing.

    Attributes:
        attribute1 (int): An example attribute.
    """

    def method1(self, param1: str) -> bool:
        """
        An example method.

        Args:
            param1 (str): A sample parameter.

        Returns:
            bool: The return value.

        Examples:
            >>> sc = SampleClass()
            >>> sc.method1("test")
        """
        return True


def test_get_markdown_from_docstring():
    expected_output = (
        "## `SampleClass`\n\n"
        "This is a sample class for testing.\n\n"
        "__Attributes:__\n\n"
        "- `attribute1` (`int`): An example attribute.\n"
        "\n### `SampleClass.method1`\n\n"
        "An example method.\n\n"
        "__Arguments:__\n\n"
        "- `param1` (`str`): A sample parameter.\n\n"
        "__Returns:__\n\n"
        "`bool`: The return value.\n\n"
        "__Examples:__\n\n"
        "```python\n"
        "sc = SampleClass()\n"
        "sc.method1(\"test\")\n"
        "```\n\n"
    )
    assert get_markdown_from_docstring(SampleClass) == expected_output
