from zrb.task_input.str_input import StrInput

entity_name_input = StrInput(
    name="entity-name",
    shortcut="e",
    description="Singular entity name",
    prompt="Singular entity name",
    default="book",
)

plural_entity_name_input = StrInput(
    name="plural-entity-name",
    description="Plural entity name",
    prompt="Plural entity name",
    default="books",
)

main_column_name_input = StrInput(
    name="column-name",
    shortcut="c",
    description="Main column name",
    prompt="Main column name",
    default="code",
)

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
