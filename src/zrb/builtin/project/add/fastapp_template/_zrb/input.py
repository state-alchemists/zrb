from fastapp_template._zrb.helper import (
    get_existing_module_names,
    get_existing_schema_names,
)

from zrb import OptionInput, StrInput
from zrb.util.string.conversion import pluralize

new_module_input = StrInput(
    name="module", description="Module name", prompt="New module name"
)

existing_module_input = OptionInput(
    name="module",
    description="Module name",
    prompt="Module name",
    options=lambda _: get_existing_module_names(),
)

new_entity_input = StrInput(
    name="entity", description="Entity name", prompt="New entity name"
)

existing_entity_input = OptionInput(
    name="entity",
    description="Entity name",
    prompt="Entity name",
    options=lambda _: get_existing_schema_names(),
)

plural_entity_input = StrInput(
    name="plural",
    description="Plural entity name",
    prompt="Plural entity name",
    default_str=lambda ctx: pluralize(ctx.input.entity),
)

new_entity_column_input = StrInput(
    name="column",
    description="Entity's column name",
    prompt="New entity's column name",
    default_str="name",
)
