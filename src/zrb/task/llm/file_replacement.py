import os
import shlex
import subprocess
import tempfile

from zrb.config.config import CFG
from zrb.task.llm.file_tool_model import FileReplacement
from zrb.util.file import read_file


def edit_replacement(
    path: str,
    replacement: list[FileReplacement] | FileReplacement,
    diff_edit_command_tpl: str | None,
) -> list[FileReplacement] | FileReplacement:
    original_content = read_file(path)
    _, extension = os.path.splitext("path")
    # Get supposed-to-be new content
    new_content = original_content
    replacement_list = [replacement] if isinstance(replacement, dict) else replacement
    for replacement in replacement_list:
        old_text = replacement["old_text"]
        new_text = replacement["new_text"]
        count = replacement.get("count", -1)
        new_content = new_content.replace(old_text, new_text, count)
    if diff_edit_command_tpl is None:
        diff_edit_command_tpl = CFG.DEFAULT_DIFF_EDIT_COMMAND_TPL
    with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as old_file:
        old_file_name = old_file.name
        old_file.write(original_content.encode())
        old_file.flush()
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as new_file:
            new_file_name = new_file.name
            new_file.write(new_content.encode())
            diff_edit_command = diff_edit_command_tpl.format(
                old=old_file_name, new=new_file_name
            )
            subprocess.call(shlex.split(diff_edit_command))
            edited_new_content = read_file(new_file_name)
    os.remove(old_file_name)
    os.remove(new_file_name)
    if edited_new_content == new_content:
        return replacement
    # TODO: optimize this
    return {
        "path": path,
        "old_text": original_content,
        "new_text": edited_new_content,
    }
