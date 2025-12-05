import difflib
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
    # Normalize input to list
    replacement_list = [replacement] if isinstance(replacement, dict) else replacement
    if not replacement_list:
        return replacement, False
    path = replacement_list[0]["path"]
    original_content = read_file(path)
    # Calculate initial proposed content based on AI's suggestion
    proposed_content = _apply_initial_replacements(original_content, replacement_list)
    # Open external editor for user modification
    edited_content = _open_diff_editor(
        path, original_content, proposed_content, diff_edit_command_tpl
    )
    # If content hasn't changed from proposal, return original replacement
    if edited_content == proposed_content:
        return replacement, False
    # Calculate optimized replacements based on user's final edit
    optimized_replacements = _generate_optimized_replacements(
        path, original_content, edited_content
    )
    return optimized_replacements, True


def _apply_initial_replacements(
    content: str, replacement_list: list[FileReplacement]
) -> str:
    new_content = content
    for single_replacement in replacement_list:
        old_text = single_replacement["old_text"]
        new_text = single_replacement["new_text"]
        count = single_replacement.get("count", -1)
        new_content = new_content.replace(old_text, new_text, count)
    return new_content


def _open_diff_editor(
    original_path: str,
    original_content: str,
    proposed_content: str,
    diff_edit_command_tpl: str | None,
) -> str:
    if diff_edit_command_tpl is None:
        diff_edit_command_tpl = CFG.DEFAULT_DIFF_EDIT_COMMAND_TPL
    _, extension = os.path.splitext(original_path)
    with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as old_file:
        old_file_name = old_file.name
        old_file.write(original_content.encode())
        old_file.flush()
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as new_file:
            new_file_name = new_file.name
            new_file.write(proposed_content.encode())
            new_file.flush()
            diff_edit_command = diff_edit_command_tpl.format(
                old=old_file_name, new=new_file_name
            )
            subprocess.call(shlex.split(diff_edit_command))
            edited_content = read_file(new_file_name)
    if os.path.exists(old_file_name):
        os.remove(old_file_name)
    if os.path.exists(new_file_name):
        os.remove(new_file_name)
    return edited_content


def _generate_optimized_replacements(
    path: str, original_content: str, edited_content: str
) -> list[FileReplacement]:
    matcher = difflib.SequenceMatcher(None, original_content, edited_content)
    hunks = _group_opcodes_into_hunks(matcher.get_opcodes())
    replacements = []
    for hunk in hunks:
        replacement = _create_replacement_from_hunk(
            path, original_content, edited_content, hunk
        )
        if replacement:
            replacements.append(replacement)
    return replacements


def _group_opcodes_into_hunks(opcodes, merge_threshold=200):
    """
    Groups opcodes into hunks.
    'equal' blocks smaller than merge_threshold are treated as context (glue) within a hunk.
    """
    hunks = []
    current_hunk = []
    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            if i2 - i1 < merge_threshold:
                if current_hunk:
                    current_hunk.append((tag, i1, i2, j1, j2))
            else:
                if current_hunk:
                    hunks.append(current_hunk)
                    current_hunk = []
        else:
            current_hunk.append((tag, i1, i2, j1, j2))
    if current_hunk:
        hunks.append(current_hunk)
    return hunks


def _create_replacement_from_hunk(
    path: str, original_content: str, edited_content: str, hunk: list
) -> FileReplacement | None:
    # Trim leading/trailing 'equal' opcodes
    while hunk and hunk[0][0] == "equal":
        hunk.pop(0)
    while hunk and hunk[-1][0] == "equal":
        hunk.pop()
    if not hunk:
        return None
    # Determine range of modification
    i_start = hunk[0][1]
    i_end = hunk[-1][2]
    j_start = hunk[0][3]
    j_end = hunk[-1][4]
    base_old_text = original_content[i_start:i_end]
    base_new_text = edited_content[j_start:j_end]
    if base_old_text == base_new_text:
        return None
    # Expand context
    start, end = _expand_context_for_uniqueness(original_content, i_start, i_end)
    start, end = _expand_to_word_boundary(original_content, start, end)
    final_old_text = original_content[start:end]
    # Reconstruct new text
    prefix = original_content[start:i_start]
    suffix = original_content[i_end:end]
    final_new_text = prefix + base_new_text + suffix
    if final_old_text == final_new_text:
        return None
    return {
        "path": path,
        "old_text": final_old_text,
        "new_text": final_new_text,
        "count": 1,
    }


def _expand_context_for_uniqueness(
    content: str, start: int, end: int
) -> tuple[int, int]:
    """Expands the range [start, end] until the substring content[start:end] is unique."""
    while content.count(content[start:end]) > 1:
        if start == 0 and end == len(content):
            break
        if start > 0:
            start -= 1
        if end < len(content):
            end += 1
    return start, end


def _expand_to_word_boundary(content: str, start: int, end: int) -> tuple[int, int]:
    """Expands the range [start, end] outwards to the nearest whitespace boundaries."""

    def is_boundary(char):
        return char.isspace()

    while start > 0 and not is_boundary(content[start - 1]):
        start -= 1
    while end < len(content) and not is_boundary(content[end]):
        end += 1
    return start, end
