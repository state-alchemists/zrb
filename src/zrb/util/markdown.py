import re


def _adjust_markdown_headers(md: str, level_change: int) -> str:
    lines = md.split("\n")
    new_lines = []
    fence_stack = []
    for line in lines:
        stripped_line = line.strip()
        fence_match = re.match(r"^([`~]{3,})", stripped_line)
        if fence_match:
            current_fence = fence_match.group(1)
            if (
                fence_stack
                and fence_stack[-1][0] == current_fence[0]
                and len(current_fence) >= len(fence_stack[-1])
            ):
                fence_stack.pop()
            else:
                fence_stack.append(current_fence)
            new_lines.append(line)
        elif fence_stack:
            new_lines.append(line)
        else:
            match = re.match(r"^(#{1,6})(\s)", line)
            if match:
                current_level = len(match.group(1))
                new_level = max(1, current_level + level_change)
                new_header = "#" * new_level + line[current_level:]
                new_lines.append(new_header)
            else:
                new_lines.append(line)
    return "\n".join(new_lines).rstrip()


def demote_markdown_headers(md: str) -> str:
    return _adjust_markdown_headers(md, level_change=1)


def make_markdown_section(header: str, content: str, as_code: bool = False) -> str:
    if content.strip() == "":
        return ""
    if as_code:
        # The fence should be one longer than the longest sequence found
        longest_backtick_sequence = 0
        for match in re.finditer(r"`+", content):
            longest_backtick_sequence = max(
                longest_backtick_sequence, len(match.group(0))
            )

        fence_len = 4
        if longest_backtick_sequence >= fence_len:
            fence_len = longest_backtick_sequence + 1
        fence = "`" * fence_len
        return f"# {header}\n{fence}\n{content.strip()}\n{fence}\n"
    return f"# {header}\n{demote_markdown_headers(content.strip())}\n"


def get_first_heading(content: str) -> str | None:
    """The text of the first `# ` heading, or `None` when there is none.

    Follows CommonMark: a heading is indented at most three spaces (four, or a
    tab, makes an indented code block), and lines inside a fenced code block
    are code, so a `# comment` in an example never becomes the title.
    """
    fence: str | None = None
    for line in content.splitlines():
        indent = len(line) - len(line.lstrip(" "))
        body = line[indent:]
        fence_match = re.match(r"(`{3,}|~{3,})(.*)", body) if indent < 4 else None
        if fence_match:
            marker, rest = fence_match.groups()
            if fence is None:
                # A backtick fence's info string may not contain a backtick.
                if not (marker[0] == "`" and "`" in rest):
                    fence = marker
                    continue
            elif (
                marker[0] == fence[0] and len(marker) >= len(fence) and not rest.strip()
            ):
                # A closing fence carries nothing but whitespace after it.
                fence = None
                continue
        if fence is None and indent < 4 and body.startswith("# "):
            return body[2:].strip()
    return None
