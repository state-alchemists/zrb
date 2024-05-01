from zrb.helper.accessories.color import colored
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked
from zrb.helper.typing import Mapping

logger.debug(colored("Loading zrb.helper.string.parse_replacment", attrs=["dark"]))


@typechecked
def parse_replacement(text: str, replacement: Mapping[str, str]):
    new_text = text
    for old, new in replacement.items():
        new_text = new_text.replace(old, new)
    return new_text
