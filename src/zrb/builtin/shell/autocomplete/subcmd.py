from zrb.builtin.group import shell_autocomplete_group
from zrb.context.context import Context
from zrb.runner.cli import cli
from zrb.task.make_task import make_task
from zrb.util.cli.subcommand import get_group_subcommands


@make_task(
    name="get-shell-subcommands",
    description="Get subcommand of any Zrb command",
    group=shell_autocomplete_group,
    alias="subcmd",
)
def get_shell_subcommands(ctx: Context):
    subcommands = get_group_subcommands(cli)
    for subcommand in subcommands:
        if subcommand.paths == ctx.args:
            return " ".join(subcommand.nexts)
    return ""
