import re


def _demote_markdown_headers(md: str) -> str:
    def demote(match):
        hashes = match.group(1)
        return "#" + hashes + match.group(2)  # add one `#`

    # Replace headers at the beginning of a line
    return re.sub(r"^(#{1,6})(\s)", demote, md, flags=re.MULTILINE)


def make_prompt_section(header: str, content: str, as_code: bool = False) -> str:
    if content.strip() == "":
        return ""
    if as_code:
        return f"# {header}\n````\n{content.strip()}\n````\n"
    return f"# {header}\n{_demote_markdown_headers(content.strip())}\n"
