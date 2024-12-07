from zrb import Group
from zrb.builtin.group import project_group

app_group = project_group.add_group(
    Group(name="fastapp", description="🚀 Managing Fastapp")
)

app_run_group = app_group.add_group(Group(name="run", description="🟢 Run Fastapp"))

app_migrate_group = app_group.add_group(
    Group(name="migrate", description="📦 Run Fastapp DB migration")
)

app_create_group = app_group.add_group(
    Group(name="create", description="✨ Create resources for Fastapp")
)

app_create_migration_group = app_create_group.add_group(
    Group(name="migration", description="📦 Create Fastapp DB migration")
)

