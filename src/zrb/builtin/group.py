from zrb.group.group import Group
from zrb.runner.cli import cli

shell_group = cli.add_group(
    Group(name="shell", description="💬 Shell related commands")
)

shell_autocomplete_group: Group = shell_group.add_group(
    Group(name="autocomplete", description="⌨️ Shell autocomplete related commands")
)

project_group = cli.add_group(
    Group(name="project", description="📁 Project related commands")
)

add_to_project_group = project_group.add_group(
    Group(name="add", description="➕ Add things to project")
)

add_fastapp_to_project_group = add_to_project_group.add_group(
    Group(name="fastapp", description="🚀 Add Fastapp resources")
)
