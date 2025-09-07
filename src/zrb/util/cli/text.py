import os
import subprocess
import tempfile

from zrb.util.file import read_file


def edit_text(
    prompt_message: str,
    value: str,
    editor: str = "vi",
    extension: str = ".txt",
) -> str:
    prompt_message_eol = f"{prompt_message}\n"
    with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temp_file:
        temp_file_name = temp_file.name
        temp_file.write(prompt_message_eol.encode())
        # Pre-fill with default content
        if value:
            temp_file.write(value.encode())
        temp_file.flush()
        subprocess.call([editor, temp_file_name])
        # Read the edited content
        edited_content = read_file(temp_file_name)
    parts = [text.strip() for text in edited_content.split(prompt_message, 1)]
    edited_content = "\n".join(parts).lstrip()
    os.remove(temp_file_name)
    return edited_content
