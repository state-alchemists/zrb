import difflib
import re
import textwrap
from typing import Any

from zrb.util.cli.terminal import get_terminal_size


def format_diff(
    old_content: str,
    new_content: str,
    path: str,
    term_width: int | None = None,
    ui: Any | None = None,
) -> str:
    """
    Returns a markdown-formatted diff string with line numbers.
    Structure: [Marker] [LineNo] [Content]
    This preserves syntax highlighting for diffs (red/green) while showing line numbers.
    Long lines are wrapped to fit within the terminal width.

    Args:
        old_content: Original file content
        new_content: New file content
        path: File path (for display purposes)
        term_width: Optional terminal width (if known)
        ui: Deprecated, kept for backward compatibility — no longer used.
    """
    diff_lines = list(
        difflib.unified_diff(
            old_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=path,
            tofile=path,
        )
    )

    if not diff_lines:
        return ""  # No changes

    formatted_lines = []

    # Track line numbers
    old_lineno = 0
    new_lineno = 0

    # Regex for hunk header: @@ -old_start,old_len +new_start,new_len @@
    hunk_re = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

    # Width for line numbers (e.g. 4)
    ln_width = 4

    # Calculate available width for content
    # Marker (1) + Space (1) + LineNo (4) + Space (2) = 8 chars prefix
    prefix_len = 1 + 1 + ln_width + 2

    # Use provided term_width or detect it
    if term_width is not None:
        calculated_width = term_width - prefix_len - 10
    else:
        try:
            # Not shutil.get_terminal_size(): the TUI redirects stdout/stderr
            # fds to a capture pipe, so that only sees a pipe and falls back to
            # 80. The robust helper falls through to stdin (fd 0, not
            # redirected) and recovers the real width.
            term_width = get_terminal_size().columns
            calculated_width = term_width - prefix_len - 10
        except Exception:
            # Default to 80 if terminal detection fails
            calculated_width = 80 - prefix_len - 10

    # Ensure minimum width of 40 chars for readability on small terminals
    # No maximum width - allow wide terminals to display long lines without wrapping
    min_content_width = 40
    content_width = max(min_content_width, calculated_width)

    for line in diff_lines:
        if line.startswith("---") or line.startswith("+++"):
            # Include file header lines as-is
            formatted_lines.append(line.rstrip("\n"))
            continue

        if line.startswith("@@"):
            match = hunk_re.match(line)
            if match:
                old_start = int(match.group(1))
                new_start = int(match.group(3))
                old_lineno = old_start - 1
                new_lineno = new_start - 1
                # Add a separator line for hunks
                formatted_lines.append(f"@@ -{old_start} +{new_start} @@")
            continue

        # Content lines
        raw_line = line[1:].rstrip("\n")  # Remove +/-/space and newline

        marker = ""
        lineno_str = ""

        if line.startswith(" "):  # Context
            old_lineno += 1
            new_lineno += 1
            marker = " "
            lineno_str = str(new_lineno)

        elif line.startswith("-"):  # Delete
            old_lineno += 1
            marker = "-"
            lineno_str = str(old_lineno)

        elif line.startswith("+"):  # Insert
            new_lineno += 1
            marker = "+"
            lineno_str = str(new_lineno)

        # Format the prefix: "M LLLL  "
        # M = marker, LLLL = line number
        lineno_field = lineno_str.rjust(ln_width)
        prefix = f"{marker} {lineno_field}  "

        # Calculate continuation prefix to preserve color and alignment
        # Continuation must start with the same marker to be colored correctly
        # by syntax highlighters. The rest is padding to match the length of
        # the original prefix.
        continuation_prefix = marker + " " * (len(prefix) - 1)

        # Wrap the content while preserving indentation
        wrapped_lines = textwrap.wrap(
            raw_line,
            width=content_width,
            replace_whitespace=False,
            drop_whitespace=False,
        )

        if not wrapped_lines:
            # Empty line
            formatted_lines.append(prefix.rstrip())
        else:
            # First line has the prefix with line number
            formatted_lines.append(f"{prefix}{wrapped_lines[0]}")
            # Subsequent lines use continuation_prefix (marker + spaces)
            for wrapped_line in wrapped_lines[1:]:
                formatted_lines.append(f"{continuation_prefix}{wrapped_line}")

    return "```diff\n" + "\n".join(formatted_lines) + "\n```"
