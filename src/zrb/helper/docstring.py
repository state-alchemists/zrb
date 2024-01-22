import inspect
import re


def get_markdown_from_docstring(cls) -> str:
    """
    Convert Google Style docstrings of a class and its methods to Markdown.

    Args:
        cls (class): The class whose docstrings are to be converted.

    Returns:
        str: The converted Markdown text.
    """
    markdown = f"## `{cls.__name__}`\n\n"
    cls_doc = get_doc(cls)
    markdown += parse_docstring(cls_doc) + "\n"
    for method_name, _ in inspect.getmembers(cls, predicate=inspect.isfunction):  # noqa
        if method_name.startswith("__"):
            # Don't parse private or protected function
            continue
        markdown += f"\n### `{cls.__name__}.{method_name}`\n\n"
        method_doc = get_method_doc(cls, method_name)
        markdown += parse_docstring(method_doc) + "\n"
    return markdown


def get_method_doc(cls, method_name: str) -> str:
    if not hasattr(cls, method_name):
        return None
    method = getattr(cls, method_name)
    if not method.__doc__ and hasattr(cls, "__bases__"):
        for parent in cls.__bases__:
            parent_method_doc = get_method_doc(parent, method_name)
            if parent_method_doc:
                return parent_method_doc
    return method.__doc__


def get_doc(cls) -> str:
    if not cls.__doc__ and hasattr(cls, "__bases__"):
        for parent in cls.__bases__:
            parent_doc = get_doc(parent)
            if parent_doc:
                return parent_doc
    return cls.__doc__


def parse_docstring(docstring: str) -> str:
    if not docstring:
        return "No documentation available.\n"
    # Split the docstring into lines
    lines = docstring.strip().split("\n")
    line_length = len(lines)
    # Process each line
    markdown_lines = []
    section = ""
    is_previous_code = False
    has_unclosed_backtick = False
    for line_index, line in enumerate(lines):
        line = line.strip()
        is_code = line.startswith(">>> ")
        is_last_line = line_index == line_length - 1
        is_new_section = False
        # Add code backticks
        if is_code and not is_previous_code:
            markdown_lines.append("```python")
            has_unclosed_backtick = True
        elif section == "examples" and is_previous_code and not is_code:
            markdown_lines.append("```")
            markdown_lines.append("")
            markdown_lines.append("```")
            has_unclosed_backtick = True
        elif is_previous_code and not is_code:
            markdown_lines.append("````")
            markdown_lines.append("")
            has_unclosed_backtick = False
        # Handle lines
        if is_code:
            markdown_lines.append(line[4:])
        elif (
            line.startswith("Attributes:")
            or line.startswith("Attribute:")
            or line.startswith("Attrs:")
            or line.startswith("Attr:")
        ):
            markdown_lines.append("__Attributes:__\n")
            section = "attributes"
            is_new_section = True
        elif (
            line.startswith("Args:")
            or line.startswith("Arg:")
            or line.startswith("Arguments:")
            or line.startswith("Argument:")
        ):
            markdown_lines.append("__Arguments:__\n")
            section = "args"
            is_new_section = True
        elif line.startswith("Returns:"):
            markdown_lines.append("__Returns:__\n")
            section = "returns"
            is_new_section = True
        elif line.startswith("Examples:") or line.startswith("Examples:"):
            markdown_lines.append("__Examples:__\n")
            section = "examples"
            is_new_section = True
        elif line == "```":
            markdown_lines.append(line)
        elif section == "args" or section == "attributes":
            named_param_match = re.match(r"^(\w+)\s+\((.+)\):(.+)$", line)
            if named_param_match:
                param_name, param_type, param_desc = named_param_match.groups()
                markdown_lines.append(
                    f"- `{param_name}` (`{param_type}`): {param_desc.strip()}"
                )
            else:
                markdown_lines.append(line)
        elif section == "returns":
            return_match = re.match(r"^(.+):(.+)$", line)
            if return_match:
                param_type, param_desc = return_match.groups()
                markdown_lines.append(f"`{param_type}`: {param_desc.strip()}")
            else:
                markdown_lines.append(line)
        else:
            markdown_lines.append(line)
        is_previous_code = is_code
        if (is_new_section or is_last_line) and has_unclosed_backtick:
            markdown_lines.append("```")
            markdown_lines.append("")
            has_unclosed_backtick = False
    return "\n".join(markdown_lines)
