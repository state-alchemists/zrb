from zrb.task_input.str_input import StrInput

column_name_input = StrInput(
    name="column-name",
    shortcut="c",
    description="Column name",
    prompt="Column name",
    default="title",
)

column_type_input = StrInput(
    name="column-type",
    shortcut="t",
    description="Column type",
    prompt="Column type",
    default="str",
)
