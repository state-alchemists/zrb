from fastapp_template._zrb.group import app_create_group

from zrb import Task

create_column = app_create_group.add_task(
    Task(name="create-app-name-column"), alias="column"
)
