from zrb.builtin.group import config_group
from zrb.context.any_context import AnyContext
from zrb.input.str_input import StrInput
from zrb.task.make_task import make_task


def _render_table(entries: list[tuple[str, str, str]]) -> str:
    """Render entries with rich's ``Table`` (not a markdown table).

    Descriptions carry intentional newlines — e.g. a knob with several options
    documents them as a bulleted list. A markdown table cannot hold a line break
    in a cell, so the previous markdown-string renderer collapsed every
    description onto one line, turning bullets into inline ``-`` fragments.
    ``Table`` cells honor ``\\n``, so the structure survives.

    Cells are wrapped in ``Text`` so their content is rendered literally: rich
    parses ``[...]`` in a plain string as console markup, which would silently
    swallow a value like ``[set]`` / ``[unset]`` (it looks like a style tag).
    """
    # lazy: heavy third-party
    from rich import box
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text

    # SIMPLE_HEAD: no top/bottom border, just a header underline. The task runner
    # prepends a status prefix to the first printed line; a box with a top border
    # would put a full-width rule on that line and overflow it. SIMPLE_HEAD opens
    # with a blank line instead, so the prefix sits clear of the table.
    table = Table(box=box.SIMPLE_HEAD, show_lines=True, pad_edge=False, expand=False)
    table.add_column("Environment Variable", style="bold bright_cyan", no_wrap=True)
    table.add_column("Value", style="green")
    table.add_column("Description")
    for env_var, value, description in entries:
        table.add_row(Text(env_var), Text(value), Text(description))

    console = Console(force_terminal=True)
    with console.capture() as capture:
        console.print(table)
    # Drop rich's trailing space-padding on each line (it pads cells out to the
    # console width). rstrip only removes whitespace, so ANSI styling — which
    # ends in 'm' — is left intact.
    return "\n".join(line.rstrip() for line in capture.get().splitlines())


def _collect_entries(keyword: str) -> list[tuple[str, str, str]]:
    # lazy: circular — builtin → config → env_field
    from zrb.config.config import CFG
    from zrb.config.env_field import EnvField

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
                    value = "" if raw is None else attr_val._serialize(raw)
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
        description="Filter keyword (optional)",
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
    ctx.print(_render_table(entries))
