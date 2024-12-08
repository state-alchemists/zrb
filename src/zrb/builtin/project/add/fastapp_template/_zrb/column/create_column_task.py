from fastapp_template._zrb.group import app_create_group

from zrb import Task

create_my_app_name_column = app_create_group.add_task(
    Task(
        name="create-my-app-name-column",
        description="📊 Create new column on an entity",
    ),
    alias="column",
)
