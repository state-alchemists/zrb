import inspect
import re


def inject_doc(markdown_file_name: str, cls):
    docstring_markdown = docstring_to_markdown(cls)
    with open(markdown_file_name, 'r') as file:
        original_content = file.read()
    pattern = r'<!--start-doc-->.*?<!--end-doc-->'
    replacement_text = '\n'.join([
        '<!--start-doc-->',
        docstring_markdown,
        '<!--end-doc-->',
    ])
    new_content = re.sub(
        pattern, replacement_text, original_content, flags=re.DOTALL
    )
    with open(markdown_file_name, 'w') as file:
        file.write(new_content)


def docstring_to_markdown(cls) -> str:
    """
    Convert Google Style docstrings of a class and its methods to Markdown.

    Args:
        cls (class): The class whose docstrings are to be converted.

    Returns:
        str: The converted Markdown text.
    """
    markdown = f"## `{cls.__name__}`\n"
    markdown += parse_docstring(cls.__doc__) + '\n'
    for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
        markdown += f"\n### `{cls.__name__}.{name}`\n"
        markdown += parse_docstring(method.__doc__)
    return markdown


def parse_docstring(docstring: str) -> str:
    if not docstring:
        return 'No documentation available.\n'
    # Split the docstring into lines
    lines = docstring.strip().split('\n')
    line_length = len(lines)
    # Process each line
    markdown_lines = []
    section = ''
    is_previous_code = False
    has_unclosed_backtick = False
    for line_index, line in enumerate(lines):
        line = line.strip()
        is_code = line.startswith('>>> ')
        is_last_line = line_index == line_length - 1
        is_new_section = False
        # Add code backticks
        if is_code and not is_previous_code:
            markdown_lines.append('```python')
            has_unclosed_backtick = True
        elif section == 'examples' and is_previous_code and not is_code:
            markdown_lines.append('```')
            markdown_lines.append('')
            markdown_lines.append('```')
            has_unclosed_backtick = True
        elif is_previous_code and not is_code:
            markdown_lines.append('````')
            markdown_lines.append('')
            has_unclosed_backtick = False
        # Handle lines
        if is_code:
            markdown_lines.append(line[4:])
        elif line.startswith('Attributes:'):
            markdown_lines.append('__Attributes:__\n')
            section = 'attributes'
            is_new_section = True
        elif line.startswith('Args:'):
            markdown_lines.append('__Arguments:__\n')
            section = 'args'
            is_new_section = True
        elif line.startswith('Returns:'):
            markdown_lines.append('__Returns:__\n')
            section = 'returns'
            is_new_section = True
        elif line.startswith('Examples:'):
            markdown_lines.append('__Examples:__\n')
            section = 'examples'
            is_new_section = True
        elif line == '```':
            markdown_lines.append(line)
        elif section == 'args' or section == 'attributes':
            named_param_match = re.match(r'^(\w+)\s+\((.+)\):(.+)$', line)
            if named_param_match:
                param_name, param_type, param_desc = named_param_match.groups()
                markdown_lines.append(
                    f'- `{param_name}` (`{param_type}`): {param_desc.strip()}'
                )
            else:
                markdown_lines.append(line)
        elif section == 'returns':
            return_match = re.match(r'^(.+):(.+)$', line)
            if return_match:
                param_type, param_desc = return_match.groups()
                markdown_lines.append(f'`{param_type}`: {param_desc.strip()}')
            else:
                markdown_lines.append(line)
        else:
            markdown_lines.append(line)
        is_previous_code = is_code
        if (is_new_section or is_last_line) and has_unclosed_backtick:
            markdown_lines.append('```')
            markdown_lines.append('')
            has_unclosed_backtick = False
    return '\n'.join(markdown_lines)
