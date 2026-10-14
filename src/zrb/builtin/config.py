import os
import shutil
import textwrap
from typing import NamedTuple

from zrb.builtin.group import config_group
from zrb.config.config import CFG
from zrb.config.env_field import EnvField
from zrb.context.any_context import AnyContext
from zrb.input.str_input import StrInput
from zrb.task.make_task import make_task
from zrb.util.cli.style import stylize_cyan, stylize_green, stylize_muted

_INDENT = "    "
_MIN_WIDTH = 60


class _Entry(NamedTuple):
    env_var: str
    value: str
    default: str
    is_set: bool
    is_secret: bool
    description: str


def _terminal_width() -> int:
    """Usable width, floored so a narrow or unknown terminal still reads."""
    return max(shutil.get_terminal_size(fallback=(100, 24)).columns, _MIN_WIDTH)


def _render_entries(entries: list[_Entry]) -> str:
    """Render entries as a definition list, one knob per block::

        ZRB_LLM_MODEL = openai:gpt-5.6-luna (set)
            Primary LLM model identifier.

    `(set)` marks a value chosen in the environment or `zrb_init.py`;
    `(default)` one zrb fell back to.

    Names run to 52 characters, too wide for columns. Each description line
    wraps independently, preserving bulleted lists.
    """
    width = _terminal_width()
    truncated_any = False
    blocks: list[str] = []
    for entry in entries:
        source = _source_label(entry)
        flat, was_truncated = _one_line_value(
            entry.value, width - len(entry.env_var) - len(source) - 4
        )
        truncated_any = truncated_any or was_truncated
        header = stylize_cyan(entry.env_var)
        if flat:
            header = f"{header} = {stylize_green(flat)}"
        header = f"{header} {stylize_muted(source)}"
        lines = [header]
        lines.extend(_wrap_description(entry.description, width))
        blocks.append("\n".join(lines))
    rendered = "\n\n".join(blocks)
    if truncated_any:
        rendered += "\n\n" + stylize_muted(
            f"Some values are shortened. Run `{CFG.ROOT_GROUP_NAME} config explain <NAME>` "
            "for one knob to see its full value."
        )
    return rendered


def _render_detail(entry: _Entry) -> str:
    """Full, untruncated view of a single knob.

    Shown when a filter narrows to one entry; value lines are verbatim, so a
    multi-line value such as ``ZRB_BANNER`` keeps its shape.
    """
    lines = [stylize_cyan(entry.env_var), ""]
    lines.append(stylize_muted(f"Value {_source_label(entry)}:"))
    lines.extend(_verbatim_lines(entry.value))
    if entry.is_set and not entry.is_secret:
        lines.extend(["", stylize_muted("Default:")])
        lines.extend(_verbatim_lines(entry.default))
    if entry.description.strip():
        lines.extend(["", stylize_muted("Description:")])
        lines.extend(_wrap_description(entry.description, _terminal_width()))
    return "\n".join(lines)


def _verbatim_lines(value: str) -> list[str]:
    if value == "":
        return [f"{_INDENT}{stylize_muted('(empty)')}"]
    return [f"{_INDENT}{stylize_green(line)}" for line in value.splitlines()]


def _source_label(entry: _Entry) -> str:
    return "(set)" if entry.is_set else "(default)"


def _one_line_value(value: str, budget: int) -> tuple[str, bool]:
    """Collapse *value* to a single line within *budget*, flagging truncation."""
    flat = " ".join(value.split())
    budget = max(budget, 20)
    if len(flat) <= budget:
        return flat, len(flat) != len(value.strip())
    return flat[: budget - 1] + "…", True


def _wrap_description(description: str, width: int) -> list[str]:
    """Wrap each source line separately so bulleted options stay bulleted."""
    out: list[str] = []
    for raw_line in description.splitlines():
        if not raw_line.strip():
            out.append("")
            continue
        out.extend(
            textwrap.wrap(
                raw_line,
                width=width,
                initial_indent=_INDENT,
                subsequent_indent=_INDENT,
            )
            or [_INDENT + raw_line.strip()]
        )
    return out


def _collect_entries(keyword: str) -> list[_Entry]:
    seen: set[str] = set()
    entries: list[_Entry] = []
    kw = keyword.lower()

    for cls in type(CFG).__mro__:
        for attr_name, attr_val in vars(cls).items():
            if not isinstance(attr_val, EnvField) or attr_name in seen:
                continue
            seen.add(attr_name)
            env_var = attr_val.env_key(CFG.ENV_PREFIX)
            default = ""
            try:
                raw = getattr(CFG, attr_name)
                if attr_val.secret:
                    # Never display a secret; only whether it is configured.
                    value = "[set]" if raw not in (None, "") else "[unset]"
                else:
                    value = "" if raw is None else attr_val.serialize(raw)
                    default = attr_val.get_default(CFG)
            except Exception:
                value = "(error)"
            description = (attr_val.__doc__ or "").replace(
                "{ENV_PREFIX}", CFG.ENV_PREFIX
            )
            if kw and kw not in env_var.lower() and kw not in description.lower():
                continue
            # An empty value reads as the default, so it is not a choice.
            is_set = any(
                os.environ.get(key) for key in attr_val.get_read_keys(CFG.ENV_PREFIX)
            )
            entries.append(
                _Entry(env_var, value, default, is_set, attr_val.secret, description)
            )

    return sorted(entries, key=lambda entry: entry.env_var)


@make_task(
    name="explain",
    description="📖 Show configuration reference",
    input=StrInput(
        name="keyword",
        description="Filter by name or description (optional)",
        prompt="Keyword to filter (leave empty for all)",
        default="",
        always_prompt=False,
    ),
    retries=0,
    group=config_group,
    alias="explain",
)
def explain_config(ctx: AnyContext) -> None:
    entries = _collect_entries(ctx.input.keyword)
    if not entries:
        ctx.print("No matching configuration entries found.")
        return
    # One match: show it in full, nothing elided.
    if len(entries) == 1:
        ctx.print(_render_detail(entries[0]), plain=True)
        return
    ctx.print(_render_entries(entries), plain=True)
