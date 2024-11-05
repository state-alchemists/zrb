from ....group.group import Group
from .._group import shell_group

shell_autocomplete_group: Group = shell_group.add_group(
    Group(name="autocomplete", description="Shell autocomplete related commands")
)
