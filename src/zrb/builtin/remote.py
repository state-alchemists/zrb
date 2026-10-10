from collections.abc import Sequence

from zrb.builtin.group import remote_group
from zrb.context.any_context import AnyContext
from zrb.input.int_input import IntInput
from zrb.input.option_input import OptionInput
from zrb.input.str_input import StrInput
from zrb.remote.execution import (
    create_probe_script,
    parse_probe_output,
    run_on_hosts,
)
from zrb.remote.inventory import Host, host_inventory, target_inventory
from zrb.remote.report import create_markdown_table, render_table
from zrb.task.make_task import make_task

_host_labels_input = OptionInput(
    name="host-labels",
    description="Host label; empty = all hosts",
    prompt="Host label",
    options=lambda _: host_inventory.get_labels(),
    allow_empty=True,
)
_format_input = OptionInput(
    name="format",
    description="table: rendered, markdown: raw markdown",
    default="table",
    options=["table", "markdown"],
)
_concurrency_input = IntInput(
    name="concurrency", description="Hosts handled at once", default=10
)
_timeout_input = IntInput(
    name="timeout", description="Seconds allowed per host", default=60
)


def _split_labels(text: str) -> list[str]:
    return [label.strip() for label in text.split(",") if label.strip()]


def _select_hosts(ctx: AnyContext) -> list[Host]:
    hosts = host_inventory.select(_split_labels(ctx.input.host_labels))
    if not hosts:
        raise ValueError(
            "[SYSTEM SUGGESTION] No host matches the given labels. Register hosts "
            "with `host_inventory.add(Host(...))` in zrb_init.py."
        )
    return hosts


def _format(ctx: AnyContext, headers: Sequence[str], rows: Sequence[Sequence[str]]):
    if ctx.input.format == "markdown":
        return create_markdown_table(headers, rows)
    return render_table(headers, rows)


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
    rows = [
        [r.host.name, "✅" if r.ok else "❌", r.output or "(no output)"]
        for r in results
    ]
    return _format(ctx, ["Host", "Status", "Output"], rows)


@make_task(
    name="remote-check",
    description="🔌 Check whether every selected host can reach every selected target",
    group=remote_group,
    alias="check",
    input=[
        _host_labels_input,
        OptionInput(
            name="target-labels",
            description="Target label; empty = all targets",
            prompt="Target label",
            options=lambda _: target_inventory.get_labels(),
            allow_empty=True,
        ),
        _format_input,
        _concurrency_input,
        _timeout_input,
    ],
)
async def remote_check(ctx: AnyContext) -> str:
    hosts = _select_hosts(ctx)
    targets = target_inventory.select(_split_labels(ctx.input.target_labels))
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
    )
    rows = [
        [r.host.name, *(_describe(s) for s in parse_probe_output(r.output, len(targets)))]
        for r in results
    ]
    return _format(ctx, ["Host", *(t.name for t in targets)], rows)


def _describe(status: str) -> str:
    if status == "n/a":
        return "➖ n/a"
    if status in ("fail", "error"):
        return f"❌ {status}"
    return f"✅ {status}"
