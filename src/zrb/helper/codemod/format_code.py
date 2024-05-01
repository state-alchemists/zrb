import autopep8

from zrb.helper.accessories.color import colored
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked

logger.debug(colored("Loading zrb.helper.codemod.format_code", attrs=["dark"]))


@typechecked
def format_code(code: str) -> str:
    return autopep8.fix_code(code)
