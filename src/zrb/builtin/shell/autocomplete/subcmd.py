from ....runner.cli import cli
from ....session.context import Context
from ....task.make_task import make_task
from ....util.cli.autocomplete.subcommand import get_group_subcommands
from ._group import shell_autocomplete_group


@make_task(
    name="get-shell-subcommands",
    description="Create Zrb autocomplete script for bash",
)
def get_shell_subcommands(ctx: Context):
    subcommands = get_group_subcommands(cli)
    for subcommand in subcommands:
        if subcommand.paths == ctx.args:
            return " ".join(subcommand.nexts)
    return ""


shell_autocomplete_group.add_task(get_shell_subcommands, "subcmd")
