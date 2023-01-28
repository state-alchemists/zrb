import random
import string


def get_random_icon() -> str:
    icons = [
        '🐶', '🐱', '🐭', '🐹', '🦊', '🐻', '🐨', '🐯', '🦁', '🐮', '🐷', '🍎', '🍐',
        '🍊', '🍋', '🍌', '🍉', '🍇', '🍓', '🍈', '🍒', '🍑'
    ]
    return random.choice(icons)


def get_random_color():
    colors = [
        'green', 'yellow', 'blue', 'magenta', 'cyan',
        'light_grey', 'dark_grey', 'light_green', 'light_yellow',
        'light_blue', 'light_magenta', 'light_cyan'
    ]
    return random.choice(colors)


def get_random_name(
    separator: str = '-',
    add_random_digit: bool = True,
    digit_count: int = 3
) -> str:
    prefixes = [
        "aurum", "argentum", "platinum", "mercurius", "sulfur", "sal",
        "luna", "sol", "ferrum", "cuprum"
    ]
    suffixes = [
        "philosophorum", "spiritus", "tinctura", "essentia", "elixir",
        "praeparatum", "aether", "vitae", "lapis", "metallum"
    ]
    prefix = random.choice(prefixes)
    suffix = random.choice(suffixes)
    parts = [prefix, suffix]
    if add_random_digit:
        random_digit = ''.join(
            random.choices(string.ascii_lowercase, k=digit_count)
        )
        parts.append(random_digit)
    return separator.join(parts)
