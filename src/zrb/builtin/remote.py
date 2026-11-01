import json
from collections.abc import Sequence

from zrb.builtin.group import remote_group
from zrb.config.env_field import comma_list
from zrb.context.any_context import AnyContext
from zrb.input.int_input import IntInput
from zrb.input.option_input import OptionInput
from zrb.input.str_input import StrInput
from zrb.remote.execution import create_probe_script, parse_probe_output, run_on_hosts
from zrb.remote.inventory import Host, host_inventory, target_inventory
from zrb.remote.report import create_csv, create_markdown_table, render_table
from zrb.task.make_task import make_task
from zrb.util.cli.style import stylize_green, stylize_red
from zrb.util.clipboard import copy_text

_host_labels_input = OptionInput(
    name="host-labels",
    description="Host label or name; empty = all hosts",
    prompt="Host label or name",
    options=lambda _: host_inventory.get_choices(),
    allow_empty=True,
)
_format_input = OptionInput(
    name="format",
    description=(
        "table: rendered, markdown: raw markdown, json: raw statuses, csv: plain "
        "rows. markdown, json and csv are also copied to the clipboard"
    ),
    default="table",
    options=["table", "markdown", "json", "csv"],
)
_concurrency_input = IntInput(
    name="concurrency", description="Hosts handled at once", default=10
)
_timeout_input = IntInput(
    name="timeout", description="Seconds allowed per host", default=60
)


def _select_hosts(ctx: AnyContext) -> list[Host]:
    hosts = host_inventory.select(comma_list(ctx.input.host_labels))
    if not hosts:
        raise ValueError(
            "[SYSTEM SUGGESTION] No host matches the given labels. Register hosts "
            "with `host_inventory.add(Host(...))` in zrb_init.py."
        )
    return hosts


def _format(
    ctx: AnyContext,
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    records: Sequence[dict[str, object]],
    plain_headers: Sequence[str],
    plain_rows: Sequence[Sequence[str]],
) -> str:
    """Render in the chosen format; csv takes the emoji-free `plain_*` cells."""
    fmt = ctx.input.format
    if fmt == "json":
        text = json.dumps(records, indent=2, ensure_ascii=False)
    elif fmt == "csv":
        text = create_csv(plain_headers, plain_rows)
    elif fmt == "markdown":
        text = create_markdown_table(headers, rows)
    else:
        return render_table(headers, rows)
    _copy_to_clipboard(ctx, text)
    return text


def _copy_to_clipboard(ctx: AnyContext, text: str) -> None:
    if copy_text(text):
        ctx.print(stylize_green("📋 Copied to clipboard"))
    else:
        ctx.print(stylize_red("❗ Could not access clipboard, please copy manually"))


@make_task(
    name="remote-run",
    description="💻 Run a command on every selected host",
    group=remote_group,
    alias="run",
    input=[
        _host_labels_input,
        StrInput(name="command", description="Command to run", prompt="Command"),
        _format_input,
        _concurrency_input,
        _timeout_input,
    ],
)
async def remote_run(ctx: AnyContext) -> str:
    hosts = _select_hosts(ctx)
    results = await run_on_hosts(
        hosts, ctx.input.command, ctx.input.timeout, ctx.input.concurrency
    )
    headers = ["Host", "Remote Host", "Status", "Output"]
    rows = [
        [
            r.host.name,
            r.host.remote_host or "(local)",
            "✅" if r.ok else "❌",
            r.output or "(no output)",
        ]
        for r in results
    ]
    plain_rows = [
        [r.host.name, r.host.remote_host or "", "ok" if r.ok else "failed", r.output]
        for r in results
    ]
    records = [
        {
            "host": r.host.name,
            "remote_host": r.host.remote_host,
            "ok": r.ok,
            "output": r.output,
        }
        for r in results
    ]
    return _format(ctx, headers, rows, records, headers, plain_rows)


@make_task(
    name="remote-check",
    description="🔌 Check whether every selected host can reach every selected target",
    group=remote_group,
    alias="check",
    input=[
        _host_labels_input,
        OptionInput(
            name="target-labels",
            description="Target label or name; empty = all targets",
            prompt="Target label or name",
            options=lambda _: target_inventory.get_choices(),
            allow_empty=True,
        ),
        _format_input,
        _concurrency_input,
        _timeout_input,
    ],
)
async def remote_check(ctx: AnyContext) -> str:
    hosts = _select_hosts(ctx)
    targets = target_inventory.select(comma_list(ctx.input.target_labels))
    if not targets:
        raise ValueError(
            "[SYSTEM SUGGESTION] No target matches the given labels. Register "
            "targets with `target_inventory.add(Target(...))` in zrb_init.py."
        )
    results = await run_on_hosts(
        hosts,
        create_probe_script(targets),
        ctx.input.timeout,
        ctx.input.concurrency,
        posix_only=True,
    )
    statuses = [parse_probe_output(r.output, len(targets)) for r in results]
    rows = [
        [r.host.name, r.host.remote_host or "(local)", *(_describe(s) for s in row)]
        for r, row in zip(results, statuses)
    ]
    plain_rows = [
        [r.host.name, r.host.remote_host or "", *row]
        for r, row in zip(results, statuses)
    ]
    records = [
        {
            "host": r.host.name,
            "remote_host": r.host.remote_host,
            "targets": {t.name: s for t, s in zip(targets, row)},
            "target_addresses": {t.name: t.get_address() for t in targets},
        }
        for r, row in zip(results, statuses)
    ]
    headers = [
        "Host",
        "Remote Host",
        *(f"{t.name}\n{t.get_address()}" for t in targets),
    ]
    plain_headers = [
        "Host",
        "Remote Host",
        *(f"{t.name} ({t.get_address()})" for t in targets),
    ]
    return _format(ctx, headers, rows, records, plain_headers, plain_rows)


_FAILED_STATUSES = ("refused", "timeout", "dns", "fail", "error")


def _describe(status: str) -> str:
    if status == "n/a":
        return "➖ n/a"
    if status in _FAILED_STATUSES:
        return f"❌ {status}"
    return f"✅ {status}"
