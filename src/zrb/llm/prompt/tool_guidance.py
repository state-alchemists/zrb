from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic_ai.models import Model

ToolCatalogue = dict[str, tuple[str | None, str | None]]
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
    extra_sections: list[str] | None = None,
) -> str:
    """
    Renders a compact tool guidance section.

    Format:
        # Tool Usage Guide
        <extra sections, e.g. parallel-tool-call policy>
        ## Group
        - **ToolName**: use_when
          * key_rule (if present)

    *extra_sections* — pre-rendered Markdown blocks (typically starting with
    ``## Heading``) inserted before the per-tool catalogue. Used by callers
    that need to surface model-aware policies (e.g.
    :func:`get_parallel_tool_call_section`).

    Only emits guidance for tools that are both in `tool_names` and `catalogue`.
    Entries with neither `use_when` nor `key_rule` are skipped. (Authoring
    note: register an entry only when it answers a cross-tool choice or
    carries a non-obvious rule — anything else is prompt weight; per-tool
    intrinsics belong in the tool docstring.)
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
                sections.append(f"## {group_label}\n" + "\n".join(group_lines))

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
    # lazy: zrb internal (heavy via transitive / circular)
    from zrb.llm.util.capabilities import is_known_model, model_capabilities

    if model is None or not is_known_model(model):
        return ""
    caps = model_capabilities.get(model)
    flag: Any = caps.supports_parallel_tool_calls
    if flag is False:
        return (
            "## Tool Call Parallelism\n"
            "- This model does not support parallel tool calls. "
            "Emit one tool call per response; for N actions, send N responses."
        )
    if flag is True:
        return (
            "## Tool Call Parallelism\n"
            "- For independent reads/searches with no inter-dependency, "
            "batch into one response with multiple tool calls. "
            "Sequence dependent writes."
        )
    return ""
