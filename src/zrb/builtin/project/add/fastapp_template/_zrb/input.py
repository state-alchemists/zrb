from fastapp_template._zrb.helper import get_existing_module_names

from zrb import OptionInput, StrInput

new_module_input = StrInput(
    name="module", description="Module name", prompt="New module name"
)

existing_module_input = OptionInput(
    name="module",
    description="Module name",
    prompt="Module name",
    options=lambda ctx: get_existing_module_names(),
)
