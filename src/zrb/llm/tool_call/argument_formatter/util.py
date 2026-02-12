import difflib
import re
import shutil
import textwrap


def format_diff(old_content: str, new_content: str, path: str) -> str:
    """
    Returns a markdown-formatted diff string with line numbers.
    Structure: [Marker] [LineNo] [Content]
    This preserves syntax highlighting for diffs (red/green) while showing line numbers.
    Long lines are wrapped to fit within the terminal width.
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
    try:
        term_width = shutil.get_terminal_size().columns
        # Reserve some space for borders/padding (e.g. 10 chars)
        content_width = max(40, term_width - prefix_len - 10)
    except Exception:
        content_width = 80

    for line in diff_lines:
        if line.startswith("---") or line.startswith("+++"):
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
