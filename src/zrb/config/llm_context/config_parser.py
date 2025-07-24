import re

from zrb.util.llm.prompt import promote_markdown_headers


def markdown_to_dict(markdown: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current_title = ""
    current_content: list[str] = []
    fence_stack: list[str] = []

    fence_pattern = re.compile(r"^([`~]{3,})(.*)$")
    h1_pattern = re.compile(r"^# (.+)$")

    for line in markdown.splitlines():
        # Detect code fence open/close
        fence_match = fence_pattern.match(line.strip())

        if fence_match:
            fence = fence_match.group(1)
            if fence_stack and fence_stack[-1] == fence:
                fence_stack.pop()  # close current fence
            else:
                fence_stack.append(fence)  # open new fence

        # Only parse H1 when not inside a code fence
        if not fence_stack:
            h1_match = h1_pattern.match(line)
            if h1_match:
                # Save previous section
                if current_title:
                    sections[current_title] = "\n".join(current_content).strip()
                # Start new section
                current_title = h1_match.group(1).strip()
                current_content = []
                continue

        current_content.append(line)

    # Save final section
    if current_title:
        sections[current_title] = "\n".join(current_content).strip()
    return {
        header: promote_markdown_headers(content)
        for header, content in sections.items()
    }
