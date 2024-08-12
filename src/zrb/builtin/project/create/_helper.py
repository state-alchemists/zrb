import os

from zrb.task.resource_maker import ResourceMaker


def copy_resource_replacement_mutator(
    task: ResourceMaker, replacements: dict[str, str]
) -> dict[str, str]:
    replacements["zrbBaseProjectDir"] = os.path.basename(
        replacements.get("zrbProjectDir", "")
    )
    if replacements.get("zrbProjectName", "") == "":
        replacements["zrbProjectName"] = replacements.get("zrbBaseProjectDir", "")
    return replacements
