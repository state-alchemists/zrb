from zrb.helper.accessories.color import colored
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked

logger.debug(colored("Loading zrb.helper.string.modification", attrs=["dark"]))


@typechecked
def double_quote(text: str) -> str:
    return '"' + text.replace('"', '\\"') + '"'
