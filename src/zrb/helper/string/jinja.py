from typing import Any

from zrb.helper.accessories.color import colored
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked

logger.debug(colored("Loading zrb.helper.string.jinja", attrs=["dark"]))


@typechecked
def is_probably_jinja(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    if "{{" in value and "}}" in value:
        return True
    if "{%" in value and "%}" in value:
        return True
    return False
