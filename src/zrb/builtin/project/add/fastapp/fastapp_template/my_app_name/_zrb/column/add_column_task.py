from my_app_name._zrb.format_task import format_my_app_name_code
from my_app_name._zrb.group import app_create_group

from zrb import Task

add_my_app_name_column = app_create_group.add_task(
    Task(
        name="add-my-app-name-column",
        description="📊 Create new column on an entity",
        successor=format_my_app_name_code,
        retries=0,
    ),
    alias="column",
)
