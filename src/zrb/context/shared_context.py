from typing import Any
from .any_shared_context import AnySharedContext
from ..dot_dict.dot_dict import DotDict
from ..xcom.xcom import Xcom
from ..config import LOGGING_LEVEL, SHOW_TIME
from ..util.string.format import fstring_format
from ..util.string.conversion import (
    to_boolean, to_camel_case, to_human_case, to_kebab_case, to_pascal_case, to_snake_case
)

import datetime


class SharedContext(AnySharedContext):
    def __init__(
        self,
        input: dict[str, Any] = {},
        args: list[Any] = [],
        env: dict[str, str] = {},
        xcom: dict[str, Xcom] = {},
        logging_level: int = LOGGING_LEVEL,
        show_time: bool = SHOW_TIME,
    ):
        self.__logging_level = logging_level
        self.__show_time = show_time
        self._input = DotDict(input)
        self._args = args
        self._env = DotDict(env)
        self._xcom = DotDict(xcom)

    def __repr__(self):
        class_name = self.__class__.__name__
        input = self._input
        args = self._args
        env = self._env
        xcom = self._xcom
        return f"<{class_name} input={input} args={args} xcom={xcom} env={env}>"

    @property
    def input(self) -> DotDict:
        return self._input

    @property
    def env(self) -> DotDict:
        return self._env

    @property
    def args(self) -> list[Any]:
        return self._args

    @property
    def xcom(self) -> DotDict[str, Xcom]:
        return self._xcom

    def get_logging_level(self) -> int:
        return self.__logging_level

    def should_show_time(self) -> bool:
        return self.__show_time

    def render(self, template: str) -> str:
        return fstring_format(
            template=template,
            data={
                "ctx": self,
                "datetime": datetime,
                "Xcom": Xcom,
                "to_boolean": to_boolean,
                "to_camel_case": to_camel_case,
                "to_human_case": to_human_case,
                "to_kebab_case": to_kebab_case,
                "to_pascal_case": to_pascal_case,
                "to_snake_case": to_snake_case
            }
        )
