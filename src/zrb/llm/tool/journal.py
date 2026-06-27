import os
import re
import shutil
import subprocess
from typing import Any

from zrb.config.config import CFG
from zrb.util.truncate import truncate_text


def search_journal(query: str, case_sensitive: bool = False) -> dict[str, Any]:
    """
    Searches for a regex pattern across all journal files in the configured journal directory.

    Returns matching lines with file names and line numbers.
    `case_sensitive=False` (default): case-insensitive search.
    """
    journal_dir = CFG.LLM_JOURNAL_DIR
    if not journal_dir:
        return {
            "error": "Journal directory is not configured (LLM_JOURNAL_DIR is unset)."
        }

    abs_dir = os.path.abspath(os.path.expanduser(journal_dir))
    if not os.path.isdir(abs_dir):
        return {"error": f"Journal directory not found: {journal_dir}"}

    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        pattern = re.compile(query, flags)
    except re.error as e:
        return {"error": f"Invalid regex pattern: {e}"}

    if shutil.which("rg"):
        return _search_with_rg(query, abs_dir, case_sensitive, pattern)
    return _search_with_python(query, abs_dir, pattern)


def _search_with_rg(
    query: str, abs_dir: str, case_sensitive: bool, pattern: re.Pattern
) -> dict[str, Any]:
    cmd = ["rg", "--with-filename", "--line-number", "--no-heading", "--no-messages"]
    if not case_sensitive:
        cmd.append("--ignore-case")
    cmd.extend(["--", query, abs_dir])

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (subprocess.TimeoutExpired, OSError) as e:
        return {"error": f"rg failed: {e}"}

    if proc.returncode == 2:
        return {"error": f"rg error: {proc.stderr.strip()}"}

    return _format_results(proc.stdout.splitlines(), abs_dir)


def _search_with_python(
    query: str, abs_dir: str, pattern: re.Pattern
) -> dict[str, Any]:
    raw_lines: list[str] = []
    for root, dirs, files in os.walk(abs_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for filename in files:
            if filename.startswith("."):
                continue
            file_path = os.path.join(root, filename)
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, 1):
                        if pattern.search(line):
                            rel = os.path.relpath(file_path, abs_dir)
                            raw_lines.append(f"{rel}:{line_num}:{line.rstrip()}")
            except OSError:
                # Unreadable file (permissions, race) — skip it, keep scanning.
                pass
    return _format_results(raw_lines, abs_dir)


def _format_results(raw_lines: list[str], abs_dir: str) -> dict[str, Any]:
    results = []
    for line in raw_lines:
        parts = line.split(":", 2)
        if len(parts) < 3:
            continue
        file_path, line_num_str, content = parts
        rel = (
            os.path.relpath(file_path, abs_dir)
            if os.path.isabs(file_path)
            else file_path
        )
        truncated, _ = truncate_text(content, 500, keep="head")
        results.append({"file": rel, "line": line_num_str, "content": truncated})

    if not results:
        return {"summary": "No matches found.", "results": []}

    return {"summary": f"Found {len(results)} matches.", "results": results}
