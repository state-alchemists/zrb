from my_app_name._zrb.format_task import format_my_app_name_code
from my_app_name._zrb.group import app_create_group
from my_app_name._zrb.input import new_column_input, new_column_type_input 

from zrb import AnyContext, make_task, Task


@make_task(
    name="update-my-app-name-schema",
    input=[
        new_column_input,
        new_column_type_input,
    ],
)
def update_my_app_name_schema(ctx: AnyContext):
    pass


add_my_app_name_column = app_create_group.add_task(
    Task(
        name="add-my-app-name-column",
        description="📊 Create new column on an entity",
        successor=format_my_app_name_code,
        retries=0,
    ),
    alias="column",
)
