from typing import Any
import re


def coalesce(value: Any, *alternatives: Any) -> Any:
    if value is not None and value != '':
        return value
    for alternative in alternatives:
        if alternative is not None and value != '':
            return alternative
    return ''


def to_camel_case(string: str) -> str:
    pascal = to_pascal_case(string)
    if len(pascal) == 0:
        return pascal
    return pascal[0].lower() + pascal[1:]


def to_pascal_case(string: str) -> str:
    string = _to_alphanum(string)
    return ''.join([
        x.lower().capitalize() for x in to_human_readable(string).split(' ')
    ])


def to_kebab_case(string: str) -> str:
    string = _to_alphanum(string)
    return '-'.join([
        x.lower() for x in to_human_readable(string).split(' ')
    ])


def to_snake_case(string: str) -> str:
    string = _to_alphanum(string)
    return '_'.join([
        x.lower() for x in to_human_readable(string).split(' ')
    ])


def _to_alphanum(string: str) -> str:
    return re.sub(r'[^a-zA-Z0-9]+', ' ', string)


def to_human_readable(string: str) -> str:
    string = string.replace('-', ' ').replace('_', ' ')
    parts = string.split(' ')
    new_parts = []
    for part in parts:
        new_part = ''
        for char_index, char in enumerate(part):
            is_first = char_index == 0
            is_last = char_index == len(part) - 1
            previous_char = part[char_index - 1] if not is_first else ''
            next_char = part[char_index + 1] if not is_last else ''
            if char.isupper() and char != ' ' and (
                (not is_last and next_char.islower()) or
                (not is_first and previous_char.islower())
            ):
                new_part += ' ' + char
                continue
            new_part += char
        new_part = new_part.strip(' ')
        if new_part != '':
            new_parts.append(new_part)
    return ' '.join(new_parts).strip(' ')
