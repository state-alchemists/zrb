from zrb.group.group import Group
from zrb.runner.cli import cli

base64_group = cli.add_group(Group(name="base64", description="📄 Base64 operations"))
git_group = cli.add_group(Group(name="git", description="🌱 Git related commands"))
git_branch_group = git_group.add_group(
    Group(name="branch", description="🌿 Git branch related command")
)
llm_group = cli.add_group(Group(name="llm", description="🤖 LLM operations"))
md5_group = cli.add_group(Group(name="md5", description="🔢 Md5 operations"))
todo_group = cli.add_group(Group(name="todo", description="✅ Todo management"))

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
