import os
import shlex
import subprocess
import tempfile
from typing import Any

from zrb.config.config import CFG
from zrb.task.llm.file_tool_model import FileReplacement
from zrb.util.file import read_file


def is_single_path_replacement(param: Any):
    if isinstance(param, dict):
        return _dict_has_exact_keys(
            param, {"path", "old_text", "new_text"}
        ) or _dict_has_exact_keys(param, {"path", "old_text", "new_text", "count"})
    if isinstance(param, list):
        current_path = None
        for single_replacement in param:
            if not is_single_path_replacement(single_replacement):
                return False
            if current_path is not None and current_path != single_replacement["path"]:
                return False
            current_path = single_replacement["path"]
        return True
    return False


def _dict_has_exact_keys(dictionary: dict, required_keys: set) -> bool:
    """
    Check if a dictionary contains exactly the specified keys.
    More efficient for large dictionaries.
    """
    if len(dictionary) != len(required_keys):
        return False
    return all(key in dictionary for key in required_keys)


def edit_replacement(
    replacement: list[FileReplacement] | FileReplacement,
    diff_edit_command_tpl: str | None = None,
) -> tuple[list[FileReplacement] | FileReplacement, bool]:
    replacement_list = [replacement] if isinstance(replacement, dict) else replacement
    if len(replacement) == 0:
        return replacement, False
    path = replacement_list[0]["path"]
    original_content = read_file(path)
    _, extension = os.path.splitext(path)
    # Get supposed-to-be new content
    new_content = original_content
    for single_replacement in replacement_list:
        old_text = single_replacement["old_text"]
        new_text = single_replacement["new_text"]
        count = single_replacement.get("count", -1)
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
            new_file.flush()
            diff_edit_command = diff_edit_command_tpl.format(
                old=old_file_name, new=new_file_name
            )
            subprocess.call(shlex.split(diff_edit_command))
            edited_new_content = read_file(new_file_name)
    os.remove(old_file_name)
    os.remove(new_file_name)
    if edited_new_content == new_content:
        return replacement, False
    # TODO: Optimize
    return {
        "path": path,
        "old_text": original_content,
        "new_text": edited_new_content,
    }, True
