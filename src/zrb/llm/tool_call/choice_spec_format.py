"""Numbered-text rendering of a `ChoiceSpec`, for UIs without an interactive picker."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from zrb.llm.ui.any_ui import ChoiceSpec


def format_choice_spec(spec: "ChoiceSpec | dict[str, Any]") -> str:
    """Render a `ChoiceSpec` as numbered text (fallback for non-widget UIs)."""
    multi = bool(spec.get("multi_select"))
    idx = spec.get("index", 1)
    total = spec.get("total", 1)
    counter = f"{idx}/{total}" if total > 1 else f"{idx}"
    lines: list[str] = [f"\n[Q{counter}] {spec.get('question', '')}"]
    for i, opt in enumerate(spec.get("options", []), start=1):
        label = get_option_label(opt, i - 1)
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


def get_option_label(option: Any, index: int) -> str:
    """*option*'s label, or ``Option N`` (1-based) when it has none."""
    label = option.get("label") if isinstance(option, dict) else None
    return str(label) if label else f"Option {index + 1}"
