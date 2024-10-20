from ...group.group import Group
from ...runner.cli import cli

shell_group = cli.add_group(
    Group(
        name="shell",
        description="Shell related commands"
    )
)
