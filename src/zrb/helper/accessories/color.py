import random

from termcolor import COLORS
from termcolor import colored as term_colored

from zrb.helper.typecheck import typechecked
from zrb.helper.typing import Iterable, Optional


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
    return term_colored(text, color, on_color, attrs)
