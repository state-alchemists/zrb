from collections.abc import Mapping
from typing import Any

from zrb.helper.accessories.color import colored
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked

logger.debug(colored("Loading zrb.helper.map.conversion", attrs=["dark"]))


@typechecked
def to_str(
    str_map: Mapping[str, Any],
    item_separator: str = "\n",
    item_prefix: str = "",
    keyval_separator: str = " : ",
) -> str:
    keys = list(str_map.keys())
    keys.sort()
    str_list = [
        item_prefix + key + keyval_separator + str(str_map[key]) for key in keys
    ]
    return item_separator.join(str_list)
