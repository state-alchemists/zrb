"""YAML frontmatter parsing for the markdown files zrb loads as definitions.

`SKILL.md` and `*.agent.md` both open with a `---`-delimited YAML block followed
by a markdown body. Both loaders open-coded the same three steps —
`startswith("---")`, `split("---", 2)`, `yaml.safe_load(parts[1])` — inside
their own try/except, and one of the two copies sat in a function already at
complexity 18.
"""

from typing import Any


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Split *content* into its frontmatter mapping and its body.

    Returns `({}, content)` when there is no frontmatter, when the block is
    unterminated, or when the YAML is not a mapping — a definition file with a
    malformed header still has a usable body, and the caller's defaults are a
    better outcome than an exception.

    Args:
        content: Full file text.

    Returns:
        `(frontmatter, body)`. The body is stripped; the frontmatter is `{}`
        rather than `None` so callers can `.get()` without a guard.

    Raises:
        yaml.YAMLError: The block is well-formed but the YAML inside it is not.
            Callers already wrap loading in try/except to skip a bad file with a
            warning, and silently treating a syntax error as "no frontmatter"
            would hide a typo'd `SKILL.md` rather than report it.
    """
    # lazy: heavy third-party — yaml pulls a C extension on some platforms and
    # this module is imported at skill/agent discovery, not at startup.
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
