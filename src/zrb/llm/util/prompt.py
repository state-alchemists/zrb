import os
import re

from zrb.config.config import CFG
from zrb.util.file import list_files, read_file
from zrb.util.markdown import make_markdown_section


def expand_prompt(prompt: str) -> str:
    """
    Expands @reference patterns in the prompt into a Reference + Appendix style.
    Example: "Check @main.py" -> "Check main.py (see Appendix)\n...[Appendix with content]..."
    """
    if not prompt:
        return prompt
    matches = get_path_references(prompt)
    if not matches:
        return prompt
    appendix_entries: list[str] = []
    last_idx = 0
    parts = []
    for match in matches:
        parts.append(prompt[last_idx : match.start()])
        path_ref = match.group("path")
        original_token = match.group(0)
        header, content, is_valid_ref = process_path_reference(path_ref)
        if not is_valid_ref:
            parts.append(original_token)
            last_idx = match.end()
            continue
        parts.append(f"`{path_ref}` (see Appendix)")
        appendix_entries.append(
            make_markdown_section(
                header or "",
                content=content or "",
                as_code=True,
            )
        )
        last_idx = match.end()
    parts.append(prompt[last_idx:])
    new_prompt = "".join(parts)
    if appendix_entries:
        new_prompt += make_markdown_section("Appendix", "\n\n".join(appendix_entries))
    return new_prompt


def get_path_references(prompt: str) -> list[re.Match]:
    """Every `@path` reference in *prompt*, as regex match objects."""
    if not prompt:
        return []
    # Optional single-letter drive prefix for Windows paths (`@C:\notes.md`);
    # `@word:something` still captures only "word".
    pattern = re.compile(r"@(?P<path>(?:[A-Za-z]:)?[\w~\-\./\\]+)")
    return list(pattern.finditer(prompt))


def process_path_reference(path_ref: str) -> tuple[str | None, str | None, bool]:
    """Resolve a path reference (without `@`) to ``(header, content, is_valid_ref)``."""
    expanded_path = os.path.expanduser(path_ref)
    abs_path = os.path.abspath(expanded_path)
    content = ""
    header = ""
    is_valid_ref = False
    if os.path.isfile(abs_path):
        try:
            content = read_file(abs_path)
            header = f"File Content: `{path_ref}`"
            is_valid_ref = True
        except Exception as e:
            CFG.LOGGER.debug(f"Failed to read referenced file {abs_path}: {e}")
    elif os.path.isdir(abs_path):
        try:
            file_list = list_files(abs_path, depth=2)
            content = "\n".join(file_list)
            if not content:
                content = "(Empty directory)"
            header = f"Directory Listing: `{path_ref}`"
            is_valid_ref = True
        except Exception as e:
            CFG.LOGGER.debug(f"Failed to list referenced dir {abs_path}: {e}")
    return header, content, is_valid_ref
