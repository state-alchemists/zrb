from zrb.builtin.group import config_group
from zrb.context.any_context import AnyContext
from zrb.input.str_input import StrInput
from zrb.task.make_task import make_task


def _escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _build_table(entries: list[tuple[str, str, str]]) -> str:
    lines = [
        "| Environment Variable | Value | Description |",
        "|---|---|---|",
    ]
    for env_var, value, description in entries:
        lines.append(
            f"| `{_escape_cell(env_var)}` "
            f"| `{_escape_cell(value)}` "
            f"| {_escape_cell(description)} |"
        )
    return "\n".join(lines)


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
            env_var = f"{CFG.ENV_PREFIX}_{attr_val._write_name}"
            try:
                raw = getattr(CFG, attr_name)
                value = "" if raw is None else attr_val._serialize(raw)
            except Exception:
                value = "(error)"
            description = attr_val.__doc__ or ""
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
    # lazy: heavy third-party
    from zrb.util.cli.markdown import render_markdown

    entries = _collect_entries(ctx.input.keyword)
    if not entries:
        ctx.print("No matching configuration entries found.")
        return
    table = _build_table(entries)
    ctx.print(render_markdown(table, width=None))
