from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic_ai.models import Model

ToolCatalogue = dict[str, tuple[str, str | None]]
ToolGroups = list[tuple[str, list[str]]]
GroupDescriptions = dict[str, str]


@dataclass
class ToolGuidance:
    group_name: str
    tool_name: str
    when_to_use: str | None = None
    key_rule: str | None = None
    group_description: str | None = None


def get_tool_guidance_prompt(
    tool_names: set[str] | None,
    catalogue: ToolCatalogue,
    groups: ToolGroups,
    extra_sections: list[str] | None = None,
    group_descriptions: GroupDescriptions | None = None,
) -> str:
    """
    Renders a compact tool guidance section.

    Format:
        # Tool Usage Guide
        <extra sections, e.g. parallel-tool-call policy>
        ## Group
        <group description, if registered>
        - **ToolName**: use_when
          * key_rule (if present)

    *extra_sections* — pre-rendered Markdown blocks (typically starting with
    ``## Heading``) inserted before the per-tool catalogue. Used by callers
    that need to surface model-aware policies (e.g.
    :func:`get_parallel_tool_call_section`).

    *group_descriptions* — per-group preamble text rendered between the group
    heading and its tool bullets. Used to share content across all tools in a
    group (e.g. the list of available subagents for the Delegation group).

    Only emits guidance for tools that are both in `tool_names` and `catalogue`.
    If a tool has only `use_when` (no `key_rule`), it is omitted unless the
    `use_when` contains non-obvious behavior worth noting.
    """
    sections: list[str] = []
    if extra_sections:
        sections.extend(s for s in extra_sections if s)

    if catalogue and groups:
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
                parts = [f"## {group_label}"]
                description = (
                    group_descriptions.get(group_label) if group_descriptions else None
                )
                if description:
                    parts.append(description)
                parts.append("\n".join(group_lines))
                sections.append("\n".join(parts))

    if not sections:
        return ""

    return "# Tool Usage Guide\n\n" + "\n\n".join(sections)


def get_parallel_tool_call_section(model: "str | Model | None") -> str:
    """Render a "## Tool Call Parallelism" section based on *model* capability.

    Returns ``""`` when the registry has no explicit knowledge for *model*
    (`supports_parallel_tool_calls is None`) — silent for capable-by-default
    models. Returns a loud warning when explicitly ``False``, and short
    encouragement when explicitly ``True``.
    """
    from zrb.llm.util.capabilities import is_known_model, model_capabilities

    if model is None or not is_known_model(model):
        return ""
    caps = model_capabilities.get(model)
    flag: Any = caps.supports_parallel_tool_calls
    if flag is False:
        return (
            "## No Tool Call Parallelism\n"
            "- ⛔ **CRITICAL: You SHOULD ALWAYS call tools sequentially.**\n"
            "- EMIT EXACTLY ONE tool call per response. NEVER concatenate tool "
            "names — `ReadRead`, `ReadReadRead`, `ActivateSkillRead`, `EditEdit` "
            "are NOT real tools and will ALWAYS be rejected.\n"
            "- To do N actions, send N separate responses (ONE tool call each), "
            "waiting for each result before the next. Reading 3 files = 3 "
            "separate responses with ONE `Read` each, NEVER one response with "
            "`ReadReadRead`."
        )
    if flag is True:
        return (
            "## Parallel Tool Calls Allowed\n"
            "- ✅ **You SHOULD call independent tools in parallel.** When you "
            "have multiple no-dependency actions, batch them: emit multiple "
            "tool calls in one response. Always sequence dependent calls."
        )
    return ""
