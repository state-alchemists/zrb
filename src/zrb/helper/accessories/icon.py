import random

from zrb.helper.accessories.color import colored
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked

logger.debug(colored("Loading zrb.helper.accessories.icon", attrs=["dark"]))


@typechecked
def get_random_icon() -> str:
    icons = [
        "🐶",
        "🐱",
        "🐭",
        "🐹",
        "🦊",
        "🐻",
        "🐨",
        "🐯",
        "🦁",
        "🐮",
        "🐷",
        "🍎",
        "🍐",
        "🍊",
        "🍋",
        "🍌",
        "🍉",
        "🍇",
        "🍓",
        "🍈",
        "🍒",
        "🍑",
    ]
    return random.choice(icons)
