import random
import string

PREFIXES = [
    "bold",
    "calm",
    "dark",
    "deep",
    "fast",
    "firm",
    "glad",
    "grey",
    "hard",
    "high",
    "kind",
    "late",
    "lean",
    "long",
    "loud",
    "mild",
    "neat",
    "pure",
    "rare",
    "rich",
    "safe",
    "slow",
    "soft",
    "tall",
    "thin",
    "trim",
    "vast",
    "warm",
    "weak",
    "wild",
]
SUFFIXES = [
    "arch",
    "area",
    "atom",
    "base",
    "beam",
    "bell",
    "bolt",
    "bone",
    "bulk",
    "bush",
    "cell",
    "chip",
    "clay",
    "coal",
    "coil",
    "cone",
    "cube",
    "disk",
    "dust",
    "face",
    "film",
    "foam",
    "frog",
    "fuel",
    "gate",
    "gear",
    "hall",
    "hand",
    "horn",
    "leaf",
]


def get_random_name(
    separator: str = "-", add_random_digit: bool = True, digit_count: int = 4
) -> str:
    """
    Generate a random name consisting of a prefix, a suffix, and an optional
    random digit string.

    Args:
        separator (str): The separator to join the parts of the name.
        add_random_digit (bool): Whether to append a random digit string.
        digit_count (int): The number of random digits to append if add_random_digit is True.

    Returns:
        str: The generated random name.
    """
    prefix = random.choice(PREFIXES)
    suffix = random.choice(SUFFIXES)
    parts = [prefix, suffix]
    if add_random_digit:
        random_digit = "".join(random.choices(string.digits, k=digit_count))
        parts.append(random_digit)
    return separator.join(parts)
