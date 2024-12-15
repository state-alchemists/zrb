from my_app_name._zrb.group import app_create_group

from zrb import Task

add_my_app_name_column = app_create_group.add_task(
    Task(
        name="add-my-app-name-column",
        description="📊 Create new column on an entity",
    ),
    alias="column",
)
