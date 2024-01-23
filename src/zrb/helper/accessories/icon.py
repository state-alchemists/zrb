import random

from zrb.helper.typecheck import typechecked


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
