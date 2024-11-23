from zrb import Group
from zrb.builtin import project_group

app_group = project_group.add_group(
    Group(name="app-name", description="🚀 Managing App Name")
)

app_run_group = app_group.add_group(Group(name="run", description="🟢 Run App Name"))

app_migrate_group = app_group.add_group(
    Group(name="migrate", description="📦 Run App Name DB migration")
)

app_create_group = app_group.add_group(
    Group(name="create", description="✨ Create resources for App Name")
)
