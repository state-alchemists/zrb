import re

NON_ALPHA_NUM = re.compile(r"[^a-zA-Z0-9]+")
TRUE_STRS = ["true", "1", "yes", "y", "active", "on"]
FALSE_STRS = ["false", "0", "no", "n", "inactive", "off"]


def double_quote(input_string: str) -> str:
    # Escape necessary characters: backslashes and double quotes
    escaped_string = re.sub(r'([\\"])', r"\\\1", input_string)
    # Wrap in double quotes
    return f'"{escaped_string}"'


def to_boolean(text: str) -> bool:
    if text.lower() in TRUE_STRS:
        return True
    if text.lower() in FALSE_STRS:
        return False
    raise Exception(f'Cannot infer boolean value from "{text}"')


def to_camel_case(text: str | None) -> str:
    text = str(text) if text is not None else ""
    pascal = to_pascal_case(text)
    if len(pascal) == 0:
        return pascal
    return pascal[0].lower() + pascal[1:]


def to_pascal_case(text: str | None) -> str:
    text = str(text) if text is not None else ""
    text = _to_alphanum(text)
    return "".join(
        [x.lower().capitalize() for x in _to_space_separated(text).split(" ")]
    )


def to_kebab_case(text: str | None) -> str:
    text = str(text) if text is not None else ""
    text = _to_alphanum(text)
    return "-".join([x.lower() for x in _to_space_separated(text).split(" ")])


def to_snake_case(text: str | None) -> str:
    text = str(text) if text is not None else ""
    text = _to_alphanum(text)
    return "_".join([x.lower() for x in _to_space_separated(text).split(" ")])


def _to_alphanum(text: str | None) -> str:
    text = str(text) if text is not None else ""
    return NON_ALPHA_NUM.sub(" ", text)


def to_human_case(text: str | None) -> str:
    text = str(text) if text is not None else ""
    return " ".join(
        [
            x.lower() if x.upper() != x else x
            for x in _to_space_separated(text).split(" ")
        ]
    )


def pluralize(noun: str) -> str:
    """
    Pluralize a given noun.

    Args:
        noun (str): The singular noun.

    Returns:
        str: The plural form of the noun.
    """
    # Irregular plural forms
    irregulars = {
        "foot": "feet",
        "tooth": "teeth",
        "child": "children",
        "person": "people",
        "man": "men",
        "woman": "women",
        "mouse": "mice",
        "goose": "geese",
        "ox": "oxen",
        "cactus": "cacti",
        "focus": "foci",
        "fungus": "fungi",
        "nucleus": "nuclei",
        "syllabus": "syllabi",
        "analysis": "analyses",
        "diagnosis": "diagnoses",
        "thesis": "theses",
        "crisis": "crises",
        "phenomenon": "phenomena",
        "criterion": "criteria",
    }

    # Handle irregular nouns
    if noun.lower() in irregulars:
        return irregulars[noun.lower()]
    # Handle words ending in 'y' preceded by a consonant
    if noun.endswith("y") and not re.match(r"[aeiou]y$", noun):
        return re.sub(r"y$", "ies", noun)
    # Handle words ending in 's', 'x', 'z', 'ch', or 'sh'
    if re.search(r"(s|x|z|ch|sh)$", noun):
        return noun + "es"
    # Handle words ending in 'f' or 'fe'
    if re.search(r"f$|fe$", noun):
        if noun.endswith("fe"):
            return re.sub(r"fe$", "ves", noun)
        return re.sub(r"f$", "ves", noun)
    # Handle general case for regular plurals
    return noun + "s"


def _to_space_separated(text: str | None) -> str:
    text = str(text) if text is not None else ""
    text = text.replace("-", " ").replace("_", " ")
    parts = text.split(" ")
    new_parts = []
    for part in parts:
        new_part = ""
        for char_index, char in enumerate(part):
            is_first = char_index == 0
            is_last = char_index == len(part) - 1
            previous_char = part[char_index - 1] if not is_first else ""
            next_char = part[char_index + 1] if not is_last else ""
            if (
                char.isupper()
                and char != " "
                and (
                    (not is_last and next_char.islower())
                    or (not is_first and previous_char.islower())
                )
            ):
                new_part += " " + char
                continue
            new_part += char
        new_part = new_part.strip(" ")
        if new_part != "":
            new_parts.append(new_part)
    return " ".join(new_parts).strip(" ")
