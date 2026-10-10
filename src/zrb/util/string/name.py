import random
import re
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
    """A random name: a prefix, a suffix, and an optional random digit
    string, joined by `separator`."""
    prefix = random.choice(PREFIXES)
    suffix = random.choice(SUFFIXES)
    parts = [prefix, suffix]
    if add_random_digit:
        random_digit = "".join(random.choices(string.digits, k=digit_count))
        parts.append(random_digit)
    return separator.join(parts)


def is_random_name(name: str) -> bool:
    """Whether *name* has the shape `get_random_name()` gives by default —
    a prefix, a suffix and four digits — and so was most likely generated."""
    return _RANDOM_NAME.fullmatch(name) is not None


def has_random_name_prefix(name: str) -> bool:
    """Whether *name* is a generated name, alone or followed by a `-topic`
    (`bold-arch-1234`, `bold-arch-1234-greetings`)."""
    return _RANDOM_NAME_PREFIX.fullmatch(name) is not None


def get_conversation_key(name: str) -> str:
    """The stable identity of a conversation: its generated name without a
    `-topic` (`bold-arch-1234-greetings` -> `bold-arch-1234`), else *name*.

    A conversation is renamed after its first message, but what hangs off it
    (sub-agent transcripts, live sessions) keeps this key, so a rename moves
    one history file and nothing else."""
    match = _RANDOM_NAME.match(name)
    if match and (match.end() == len(name) or name[match.end()] == "-"):
        return match.group(0)
    return name


_RANDOM_NAME = re.compile(rf"(?:{'|'.join(PREFIXES)})-(?:{'|'.join(SUFFIXES)})-\d{{4}}")
_RANDOM_NAME_PREFIX = re.compile(_RANDOM_NAME.pattern + r"(?:-.+)?")
