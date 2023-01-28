import random
import string


def get_random_icon() -> str:
    icons = [
        '🐶', '🐱', '🐭', '🐹', '🦊', '🐻', '🐨', '🐯', '🦁', '🐮', '🐷', '🍎', '🍐',
        '🍊', '🍋', '🍌', '🍉', '🍇', '🍓', '🍈', '🍒', '🍑'
    ]
    return random.choice(icons)


def get_random_name() -> str:
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
    code = ''.join(random.choices(string.ascii_lowercase, k=4))
    return '-'.join([prefix, suffix, code])
