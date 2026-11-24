"""YAML frontmatter parsing for the markdown files zrb loads as definitions.

`SKILL.md` and `*.agent.md` both open with a `---`-delimited YAML block followed
by a markdown body.
"""

from typing import Any


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Split *content* into its frontmatter mapping and its body.

    The `---` delimiters must start at column 0 (trailing whitespace is
    tolerated): an indented `---` inside a YAML block scalar is content, not a
    closer. A leading UTF-8 BOM is ignored.

    Returns `({}, content)` when there is no frontmatter, when the block is
    unterminated, or when the YAML is not a mapping. The body is stripped.

    Raises:
        yaml.YAMLError: The block is well-formed but the YAML inside it is not,
            so a typo'd `SKILL.md` is reported rather than hidden.
    """
    # lazy: heavy third-party — yaml; imported at discovery, not startup.
    import yaml

    # A BOM is metadata, not content: a caller that read the file as plain
    # UTF-8 still carries it, and it would hide the opening delimiter.
    if content.startswith("\ufeff"):
        content = content[1:]
    lines = content.splitlines()
    if not lines or lines[0].rstrip() != "---":
        return {}, content
    for index in range(1, len(lines)):
        if lines[index].rstrip() != "---":
            continue
        body = "\n".join(lines[index + 1 :]).strip()
        frontmatter = yaml.safe_load("\n".join(lines[1:index]))
        if not isinstance(frontmatter, dict):
            return {}, body
        return frontmatter, body
    return {}, content
