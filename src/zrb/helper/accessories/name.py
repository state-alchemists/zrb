import random
import string

from zrb.helper.typecheck import typechecked


@typechecked
def get_random_name(
    separator: str = "-", add_random_digit: bool = True, digit_count: int = 4
) -> str:
    prefixes = [
        "gold",
        "lead",
        "salt",
        "cold",
        "warm",
        "damp",
        "dry ",
        "dark",
        "lite",
        "fire",
        "airy",
        "deep",
        "rare",
        "rich",
        "pure",
        "soft",
        "hard",
        "mild",
        "wild",
        "vast",
        "thin",
        "thik",
        "full",
        "void",
        "firm",
        "fume",
        "dust",
        "ashy",
        "glow",
        "fade",
    ]
    suffixes = [
        "herb",
        "elix",
        "mud ",
        "ice ",
        "fog ",
        "gem ",
        "melt",
        "ore ",
        "sand",
        "soil",
        "rock",
        "rust",
        "salt",
        "slag",
        "smog",
        "wax ",
        "clay",
        "coal",
        "flam",
        "glow",
        "gale",
        "hail",
        "leaf",
        "mist",
        "moon",
        "star",
        "sulf",
        "tide",
        "vein",
        "wind",
    ]
    prefix = random.choice(prefixes)
    suffix = random.choice(suffixes)
    parts = [prefix, suffix]
    if add_random_digit:
        random_digit = "".join(random.choices(string.digits, k=digit_count))
        parts.append(random_digit)
    return separator.join(parts)
