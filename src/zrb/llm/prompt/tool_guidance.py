from __future__ import annotations

from dataclasses import dataclass

ToolCatalogue = dict[str, tuple[str, str | None]]
ToolGroups = list[tuple[str, list[str]]]


@dataclass
class ToolGuidance:
    group_name: str
    tool_name: str
    when_to_use: str | None = None
    key_rule: str | None = None


def get_tool_guidance_prompt(
    tool_names: set[str] | None,
    catalogue: ToolCatalogue,
    groups: ToolGroups,
) -> str:
    """
    Renders a compact tool guidance section.

    Format:
        ## Tool Usage Guide
        - **ToolName**: use_when
          * key_rule (if present)

    Only emits guidance for tools that are both in `tool_names` and `catalogue`.
    If a tool has only `use_when` (no `key_rule`), it is omitted unless the
    `use_when` contains non-obvious behavior worth noting.
    """
    if not catalogue or not groups:
        return ""

    sections: list[str] = []
    for group_label, members in groups:
        group_lines: list[str] = []
        for name in members:
            if tool_names is not None and name not in tool_names:
                continue
            entry = catalogue.get(name)
            if entry is None:
                continue
            use_when, key_rule = entry
            # Skip if neither use_when nor key_rule provides non-obvious info
            if not use_when and not key_rule:
                continue
            bullet = f"- **{name}**: {use_when}" if use_when else f"- **{name}**"
            if key_rule:
                bullet += f"\n  * {key_rule}"
            group_lines.append(bullet)

        if group_lines:
            sections.append(f"## {group_label}\n" + "\n".join(group_lines))

    if not sections:
        return ""

    return "# Tool Usage Guide\n\n" + "\n\n".join(sections)
