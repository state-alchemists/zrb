from typing import Any, Optional
import re
import jinja2


def _is_undefined(value: Any) -> bool:
    return value is None or isinstance(value, jinja2.Undefined)


def coalesce(value: Any, *alternatives: Any) -> Any:
    if not _is_undefined(value):
        return value
    for alternative in alternatives:
        if not _is_undefined(alternative):
            return alternative
    return None


def coalesce_str(value: Any, *alternatives: Any) -> Any:
    if not _is_undefined(value) and value != '':
        return str(value)
    for alternative in alternatives:
        if not _is_undefined(alternative) and alternative != '':
            return str(alternative)
    return ''


def to_camel_case(text: Optional[str]) -> str:
    text = str(text) if not _is_undefined(text) else ''
    pascal = to_pascal_case(text)
    if len(pascal) == 0:
        return pascal
    return pascal[0].lower() + pascal[1:]


def to_pascal_case(text: Optional[str]) -> str:
    text = str(text) if not _is_undefined(text) else ''
    text = _to_alphanum(text)
    return ''.join([
        x.lower().capitalize() for x in to_human_readable(text).split(' ')
    ])


def to_kebab_case(text: Optional[str]) -> str:
    text = str(text) if not _is_undefined(text) else ''
    text = _to_alphanum(text)
    return '-'.join([
        x.lower() for x in to_human_readable(text).split(' ')
    ])


def to_snake_case(text: Optional[str]) -> str:
    text = str(text) if not _is_undefined(text) else ''
    text = _to_alphanum(text)
    return '_'.join([
        x.lower() for x in to_human_readable(text).split(' ')
    ])


def _to_alphanum(text: Optional[str]) -> str:
    text = str(text) if not _is_undefined(text) else ''
    return re.sub(r'[^a-zA-Z0-9]+', ' ', text)


def to_human_readable(text: Optional[str]) -> str:
    text = str(text) if not _is_undefined(text) else ''
    text = text.replace('-', ' ').replace('_', ' ')
    parts = text.split(' ')
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
