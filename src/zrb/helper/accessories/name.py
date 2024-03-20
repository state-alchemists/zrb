import random
import string

from zrb.helper.typecheck import typechecked


@typechecked
def get_random_name(
    separator: str = "-", add_random_digit: bool = True, digit_count: int = 4
) -> str:
    prefixes = [
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
    suffixes = [
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
    prefix = random.choice(prefixes)
    suffix = random.choice(suffixes)
    parts = [prefix, suffix]
    if add_random_digit:
        random_digit = "".join(random.choices(string.digits, k=digit_count))
        parts.append(random_digit)
    return separator.join(parts)
