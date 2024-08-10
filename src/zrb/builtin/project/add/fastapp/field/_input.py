from zrb.task_input.choice_input import ChoiceInput
from zrb.task_input.str_input import StrInput

column_name_input = StrInput(
    name="column-name",
    shortcut="c",
    description="Column name",
    prompt="Column name",
    default="title",
)

column_type_input = ChoiceInput(
    name="column-type",
    shortcut="t",
    description="Column type",
    prompt="Column type",
    choices=[
        "string",
        "text",
        "boolean",
        "integer",
        "float",
        "double",
        "date",
        "datetime",
        "time",
    ],
    default="string",
)
