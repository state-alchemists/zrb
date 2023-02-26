import random
import string


def get_random_name(
    separator: str = '-',
    add_random_digit: bool = True,
    digit_count: int = 3
) -> str:
    prefixes = [
        "aurum", "argentum", "platinum", "mercurius", "sulfur", "sal",
        "luna", "sol", "ferrum", "cuprum", "argent", "aurora", "citrin",
        "coral", "diamond", "dragon", "emerald", "garnet", "jade", "onyx",
        "opal", "pearl", "ruby", "sapphire", "topaz", "turquoise", "verde",
        "zircon"
    ]
    suffixes = [
        "philosophorum", "spiritus", "tinctura", "essentia", "elixir",
        "praeparatum", "aether", "vitae", "lapis", "metallum", "aureum",
        "caelestis", "chrysopoeia", "cosmicum", "deum", "draconis",
        "elementorum", "hermetica", "illuminationis", "magnum", "mysticum",
        "occultum", "omnipotentis", "philosophia", "praestantissimum",
        "quintessentia", "regeneratio", "universalis"
    ]
    prefix = random.choice(prefixes)
    suffix = random.choice(suffixes)
    parts = [prefix, suffix]
    if add_random_digit:
        random_digit = ''.join(
            random.choices(string.digits, k=digit_count)
        )
        parts.append(random_digit)
    return separator.join(parts)
