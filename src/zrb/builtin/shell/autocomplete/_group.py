from .._group import shell_group
from ....group.group import Group

shell_autocomplete_group: Group = shell_group.add_group(
    Group(
        name="autocomplete",
        description="Shell autocomplete related commands"
    )
)
