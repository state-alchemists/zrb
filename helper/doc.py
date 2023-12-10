from zrb.helper.docstring import get_markdown_from_docstring
import re


def inject_doc(markdown_file_name: str, cls):
    docstring_markdown = get_markdown_from_docstring(cls)
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
