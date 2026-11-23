import os
import subprocess
import tempfile

from zrb.util.file import read_text_file


def edit_text(
    prompt_message: str,
    value: str,
    editor: str = "vi",
    extension: str = ".txt",
) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temp_file:
        temp_file_name = temp_file.name
        if prompt_message.strip() != "":
            prompt_message_eol = f"{prompt_message}\n"
            temp_file.write(prompt_message_eol.encode())
        if value:
            temp_file.write(value.encode())
        temp_file.flush()
    try:
        subprocess.call([editor, temp_file_name])
        # `read_file` would hand non-UTF-8 output back as base64. Read it as
        # text instead, so a crashed editor surfaces as an error rather than as
        # content the user never wrote.
        edited_content = read_text_file(temp_file_name)
    finally:
        os.remove(temp_file_name)
    if prompt_message.strip() != "":
        parts = [text.strip() for text in edited_content.split(prompt_message, 1)]
        edited_content = "\n".join(parts).lstrip()
    return edited_content
