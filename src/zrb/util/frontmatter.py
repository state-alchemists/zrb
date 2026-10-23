"""YAML frontmatter parsing for the markdown files zrb loads as definitions.

`SKILL.md` and `*.agent.md` both open with a `---`-delimited YAML block followed
by a markdown body.
"""

from typing import Any


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Split *content* into its frontmatter mapping and its body.

    Returns `({}, content)` when there is no frontmatter, when the block is
    unterminated, or when the YAML is not a mapping. The body is stripped.

    Raises:
        yaml.YAMLError: The block is well-formed but the YAML inside it is not,
            so a typo'd `SKILL.md` is reported rather than hidden.
    """
    # lazy: heavy third-party — yaml; imported at discovery, not startup.
    import yaml

    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, content
    for index in range(1, len(lines)):
        if lines[index].strip() != "---":
            continue
        body = "\n".join(lines[index + 1 :]).strip()
        frontmatter = yaml.safe_load("\n".join(lines[1:index]))
        if not isinstance(frontmatter, dict):
            return {}, body
        return frontmatter, body
    return {}, content
