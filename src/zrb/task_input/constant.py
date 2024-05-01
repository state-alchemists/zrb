from zrb.helper.accessories.color import colored
from zrb.helper.log import logger

logger.debug(colored("Loading zrb.task_input.constant", attrs=["dark"]))

RESERVED_INPUT_NAMES = ("_task", "_args")
