from fastapp._zrb.helper import (
    get_existing_schema_names, get_existing_module_names
)

from zrb import OptionInput, StrInput

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
