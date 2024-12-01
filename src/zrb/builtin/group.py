from zrb.group.group import Group
from zrb.runner.cli import cli

base64_group = cli.add_group(Group(name="base64", description="📄 Base64 operations"))
git_group = cli.add_group(Group(name="git", description="🌱 Git related commands"))
git_branch_group = git_group.add_group(
    Group(name="branch", description="🌿 Git branch related commands")
)
git_subtree_group = git_group.add_group(
    Group(name="subtree", description="🌳 Git subtree related commands")
)
llm_group = cli.add_group(Group(name="llm", description="🤖 LLM operations"))
md5_group = cli.add_group(Group(name="md5", description="🔢 Md5 operations"))
python_group = cli.add_group(
    Group(name="python", description="🐍 Python related commands")
)
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

setup_group = cli.add_group(Group(name="setup", description="🔧 Setup"))
setup_latex_group = setup_group.add_group(
    Group(name="latex", description="✍️ Setup LaTeX")
)
