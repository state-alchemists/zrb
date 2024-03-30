import os

from zrb.helper.typing import Mapping
from zrb.task.resource_maker import ResourceMaker


def copy_resource_replacement_mutator(
    task: ResourceMaker, replacements: Mapping[str, str]
) -> Mapping[str, str]:
    replacements["zrbBaseProjectDir"] = os.path.basename(
        replacements.get("zrbProjectDir", "")
    )
    if replacements.get("zrbProjectName", "") == "":
        replacements["zrbProjectName"] = replacements.get("zrbBaseProjectDir", "")
    return replacements
