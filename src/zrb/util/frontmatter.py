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

    if not content.startswith("---"):
        return {}, content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content
    frontmatter = yaml.safe_load(parts[1])
    if not isinstance(frontmatter, dict):
        return {}, parts[2].strip()
    return frontmatter, parts[2].strip()
