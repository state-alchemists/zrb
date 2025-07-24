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
    return "\n".join(new_lines)


def demote_markdown_headers(md: str) -> str:
    return _adjust_markdown_headers(md, level_change=1)


def promote_markdown_headers(md: str) -> str:
    return _adjust_markdown_headers(md, level_change=-1)


def make_prompt_section(header: str, content: str, as_code: bool = False) -> str:
    if content.strip() == "":
        return ""
    if as_code:
        # Find the longest sequence of backticks in the content
        longest_backtick_sequence = 0
        # Use finditer to find all occurrences of backticks
        for match in re.finditer(r"`+", content):
            longest_backtick_sequence = max(
                longest_backtick_sequence, len(match.group(0))
            )

        # The fence should be one longer than the longest sequence found
        fence_len = 4
        if longest_backtick_sequence >= fence_len:
            fence_len = longest_backtick_sequence + 1
        fence = "`" * fence_len
        return f"# {header}\n{fence}\n{content.strip()}\n{fence}\n"
    return f"# {header}\n{demote_markdown_headers(content.strip())}\n"
