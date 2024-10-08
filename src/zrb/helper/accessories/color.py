import random
from collections.abc import Iterable
from typing import Optional

from termcolor import COLORS

from zrb.helper.accessories.untyped_color import untyped_colored
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked

logger.debug(untyped_colored("Loading zrb.helper.accessories.color", attrs=["dark"]))


@typechecked
def get_random_color() -> str:
    colors = [
        "green",
        "yellow",
        "blue",
        "magenta",
        "cyan",
        "white",
        "light_green",
        "light_yellow",
        "light_blue",
        "light_magenta",
        "light_cyan",
    ]
    return random.choice(colors)


@typechecked
def is_valid_color(color: str) -> bool:
    return color in COLORS


@typechecked
def colored(
    text: str,
    color: Optional[str] = None,
    on_color: Optional[str] = None,
    attrs: Optional[Iterable[str]] = None,
) -> str:
    return untyped_colored(text, color, on_color, attrs)
