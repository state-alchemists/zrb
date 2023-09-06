from zrb.helper.typecheck import typechecked
import random


@typechecked
def get_random_icon() -> str:
    icons = [
        '🐶', '🐱', '🐭', '🐹', '🦊', '🐻', '🐨', '🐯', '🦁', '🐮', '🐷', '🍎', '🍐',
        '🍊', '🍋', '🍌', '🍉', '🍇', '🍓', '🍈', '🍒', '🍑'
    ]
    return random.choice(icons)
