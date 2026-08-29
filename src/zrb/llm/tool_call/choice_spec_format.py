"""Numbered-text rendering of a `ChoiceSpec` — the fallback used by any UI
that can't render an interactive picker (`BaseUI.ask_user_choice` in
`ui/base/ui.py`) and by `AskUserQuestion`'s own duck-typed-UI fallback in
`tool/ask.py`.

Depends only on `ChoiceSpec`'s shape (`tool_call/ui_protocol.py`, which
itself has zero `zrb.llm.*` imports), so both sides can import this at
module scope without needing the other.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from zrb.llm.tool_call.ui_protocol import ChoiceSpec


def format_choice_spec(spec: "ChoiceSpec | dict[str, Any]") -> str:
    """Render a `ChoiceSpec` as numbered text (fallback for non-widget UIs)."""
    multi = bool(spec.get("multi_select"))
    idx = spec.get("index", 1)
    total = spec.get("total", 1)
    counter = f"{idx}/{total}" if total > 1 else f"{idx}"
    lines: list[str] = [f"\n[Q{counter}] {spec.get('question', '')}"]
    for i, opt in enumerate(spec.get("options", []), start=1):
        label = opt.get("label", f"Option {i}")
        desc = opt.get("description", "")
        suffix = f" — {desc}" if desc else ""
        lines.append(f"  {i}. {label}{suffix}")
    hint = (
        "Reply with comma-separated numbers (e.g. 1,3) or free-form text: "
        if multi
        else "Reply with a number or free-form text: "
    )
    lines.append(hint)
    return "\n".join(lines)
