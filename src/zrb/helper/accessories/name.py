from zrb.helper.typecheck import typechecked
import random
import string


@typechecked
def get_random_name(
    separator: str = '-',
    add_random_digit: bool = True,
    digit_count: int = 4
) -> str:
    prefixes = [
        'albedo', 'argent', 'argentum', 'aurora', 'aurum', 'azure',
        'basilisk', 'cerulean', 'chimeric', 'citrin', 'coral', 'crimson',
        'diamond', 'draco', 'dragon', 'emerald', 'ethereal', 'ferrum',
        'flammeus', 'garnet', 'glacial', 'glimmering', 'glistening', 'golden',
        'helios', 'igneous', 'imperial', 'jade', 'luminous', 'luna', 'lunar',
        'mystic', 'nephrite', 'nocturnal', 'obsidian', 'opal', 'pearl',
        'platinum', 'prismatic', 'ruby', 'sapphire', 'serpentine', 'silver',
        'sol', 'solar', 'spiritual', 'stellar',  'tempest', 'topaz',
        'turquoise', 'verde', 'vermillion', 'vitreous', 'zephyr', 'zircon'
    ]
    suffixes = [
        'aether', 'albedo', 'alchemy', 'arcana', 'aureum', 'aetheris',
        'anima', 'astralis', 'caelestis', 'chrysopoeia', 'cosmicum',
        'crystallum', 'deum', 'divinitas', 'draconis', 'elementorum', 'elixir',
        'essentia', 'eternis', 'ethereus', 'fatum', 'flamma', 'fulgur',
        'hermetica', 'ignis', 'illuminationis', 'imperium', 'incantatum',
        'infinitum', 'lapis', 'lux', 'magicae', 'magnum', 'materia',
        'metallum', 'mysticum', 'natura', 'occultum', 'omnipotentis',
        'opulentia', 'philosophia', 'philosophorum', 'praeparatum',
        'praestantissimum', 'prima', 'primordium', 'quintessentia',
        'regeneratio', 'ritualis', 'sanctum', 'spiritus', 'tenebris',
        'terra', 'tinctura', 'transmutationis', 'universalis', 'vapores',
        'venenum', 'veritas', 'vitae', 'volatus'
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
