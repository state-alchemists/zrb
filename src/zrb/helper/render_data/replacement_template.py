from typing import Union, Mapping, List, TypeVar
from ..common import to_pascal_case
import logging


def tpl(val: str) -> str:
    return '{{' + val + '}}'


def coalesce(val: str, *alternatives: str) -> str:
    values = ', '.join([val] + list(alternatives))
    return f'zrb.coalesce({values})'


def camel(val: str) -> str:
    return f'zrb.to_camel_case({val})'


def kebab(val: str) -> str:
    return f'zrb.to_kebab_case({val})'


def snake(val: str) -> str:
    return f'zrb.to_snake_case({val})'


def pascal(val: str) -> str:
    return f'zrb.to_pascal_case({val})'


def human(val: str) -> str:
    return f'zrb.to_human_readable({val})'


TReplacement = TypeVar('TReplacement', bound='Replacement')


class Replacement():
    CAMEL = 'camel'
    PASCAL = 'pascal'
    KEBAB = 'kebab'
    SNAKE = 'snake'
    HUMAN = 'human'
    ALL = ['camel', 'pascal', 'kebab', 'snake', 'human']

    def __init__(self, replacements: Mapping[str, str] = {}):
        self.replacements = replacements
        self.tpl_map = {
            Replacement.CAMEL: camel,
            Replacement.PASCAL: pascal,
            Replacement.KEBAB: kebab,
            Replacement.SNAKE: snake,
            Replacement.HUMAN: human,
        }

    def get(self) -> Mapping[str, str]:
        logging.debug(f'Rendered replacements: {self.replacements}')
        return self.replacements

    def add_key_val(
        self, key: str, value: Union[str, List[str]]
    ) -> TReplacement:
        val = self._get_val(value)
        self.replacements[key] = tpl(val)
        return self

    def _get_val(self, value: Union[str, List[str]]) -> str:
        if isinstance(value, str):
            return value
        return coalesce(*value)

    def add_transformed_key_val(self, transformations: List[str]):
        def add_key_val(
            key: str, value: Union[str, List[str]]
        ) -> TReplacement:
            return self._add_transformed_key_val(
                transformations=transformations,
                key=key,
                value=value
            )
        return add_key_val

    def _add_transformed_key_val(
        self,
        transformations: List[str],
        key: str,
        value: Union[str, List[str]]
    ) -> TReplacement:
        for trans_name in transformations:
            if trans_name not in self.tpl_map:
                raise Exception(f'Invalid transformation {trans_name}')
            tpl_transformer = self.tpl_map[trans_name]
            new_key = to_pascal_case(f'{trans_name} {key}')
            new_val = tpl_transformer(self._get_val(value))
            self.add_key_val(new_key, new_val)
        self.add_key_val(key, value)
        return self
