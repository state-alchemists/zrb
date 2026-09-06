import shutil
import textwrap

from zrb.builtin.group import config_group
from zrb.config.config import CFG
from zrb.config.env_field import EnvField
from zrb.context.any_context import AnyContext
from zrb.input.str_input import StrInput
from zrb.task.make_task import make_task
from zrb.util.cli.style import stylize_cyan, stylize_green, stylize_muted


_INDENT = "    "
_MIN_WIDTH = 60


def _terminal_width() -> int:
    """Usable width, floored so a narrow or unknown terminal still reads."""
    return max(shutil.get_terminal_size(fallback=(100, 24)).columns, _MIN_WIDTH)


def _render_entries(entries: list[tuple[str, str, str]]) -> str:
    """Render entries as a definition list, one knob per block::

        ZRB_LLM_MODEL = openai:gpt-5.6-luna
            Primary LLM model identifier.

    A definition list rather than columns because names run to 52 characters:
    a column wide enough to hold one unwrapped leaves roughly ten for the
    description on an 80-column terminal. Stacking gives every field the full
    width, and the name — the thing being looked up — never wraps.

    Descriptions carry intentional newlines (a knob with several options
    documents them as a bulleted list), so each line wraps independently;
    reflowing the whole description as one paragraph would run the bullets
    together.
    """
    width = _terminal_width()
    truncated_any = False
    blocks: list[str] = []
    for env_var, value, description in entries:
        flat, was_truncated = _one_line_value(value, width - len(env_var) - 3)
        truncated_any = truncated_any or was_truncated
        header = stylize_cyan(env_var)
        if flat:
            header = f"{header} = {stylize_green(flat)}"
        lines = [header]
        lines.extend(_wrap_description(description, width))
        blocks.append("\n".join(lines))
    rendered = "\n\n".join(blocks)
    if truncated_any:
        rendered += "\n\n" + stylize_muted(
            "Some values are shortened. Run `zrb config explain <NAME>` "
            "for one knob to see its full value."
        )
    return rendered


def _render_detail(env_var: str, value: str, description: str) -> str:
    """Full, untruncated view of a single knob.

    Reached when a filter narrows to one entry, which makes it the escape
    hatch for the list view's shortening. Value lines are emitted verbatim
    under their own heading, so a multi-line value such as ``ZRB_BANNER``
    keeps its shape instead of being flattened to fit beside a name.
    """
    lines = [stylize_cyan(env_var), ""]
    lines.append(stylize_muted("Value:"))
    if value == "":
        lines.append(f"{_INDENT}{stylize_muted('(empty)')}")
    else:
        lines.extend(
            f"{_INDENT}{stylize_green(line)}" for line in value.splitlines() or [""]
        )
    if description.strip():
        lines.extend(["", stylize_muted("Description:")])
        lines.extend(_wrap_description(description, _terminal_width()))
    return "\n".join(lines)


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
                subsequent_indent=_INDENT + "  ",
            )
            or [_INDENT + raw_line.strip()]
        )
    return out


def _collect_entries(keyword: str) -> list[tuple[str, str, str]]:
    seen: set[str] = set()
    entries: list[tuple[str, str, str]] = []
    kw = keyword.lower()

    for cls in type(CFG).__mro__:
        for attr_name, attr_val in vars(cls).items():
            if not isinstance(attr_val, EnvField) or attr_name in seen:
                continue
            seen.add(attr_name)
            env_var = attr_val.env_key(CFG.ENV_PREFIX)
            try:
                raw = getattr(CFG, attr_name)
                if attr_val.secret:
                    # Never display a secret; only whether it is configured.
                    value = "[set]" if raw not in (None, "") else "[unset]"
                else:
                    value = "" if raw is None else attr_val.serialize(raw)
            except Exception:
                value = "(error)"
            description = (attr_val.__doc__ or "").replace(
                "{ENV_PREFIX}", CFG.ENV_PREFIX
            )
            if kw and kw not in env_var.lower() and kw not in description.lower():
                continue
            entries.append((env_var, value, description))

    return sorted(entries, key=lambda x: x[0])


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
    # A filter that narrows to exactly one knob is a request to see that knob,
    # so nothing is elided — this is how a shortened value in the list view is
    # recovered in full.
    if len(entries) == 1:
        ctx.print(_render_detail(*entries[0]))
        return
    ctx.print(_render_entries(entries))
