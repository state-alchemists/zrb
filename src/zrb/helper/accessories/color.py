from typing import Iterable, Optional
from termcolor import colored as term_colored, COLORS
import random


def get_random_color():
    colors = [
        'green', 'yellow', 'blue', 'magenta', 'cyan',
        'light_green', 'light_yellow', 'light_blue',
        'light_magenta', 'light_cyan'
    ]
    return random.choice(colors)


def is_valid_color(color: str) -> bool:
    return color in COLORS


def colored(
    text: str,
    color: Optional[str] = None,
    on_color: Optional[str] = None,
    attrs: Optional[Iterable[str]] = None
) -> str:
    return term_colored(text, color, on_color, attrs)
