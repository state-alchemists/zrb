from typing import Any
from collections.abc import Mapping
from .any_shared_context import AnySharedContext
from ..dict_to_object.dict_to_object import DictToObject
from ..xcom.xcom import Xcom
from ..config import LOGGING_LEVEL, SHOW_TIME

import datetime


def fstring_like_format(template: str, data: Mapping[str, Any]) -> str:
    # Safely evaluate the template as a Python expression
    try:
        return eval(f'f"""{template}"""', {}, data)
    except Exception:
        raise ValueError(f"Failed to parse template: {template}")


class SharedContext(AnySharedContext):
    def __init__(
        self,
        input: Mapping[str, Any] = {},
        args: list[Any] = [],
        env: Mapping[str, str] = {},
        xcom: Mapping[str, Xcom] = {},
        logging_level: int = LOGGING_LEVEL,
        show_time: bool = SHOW_TIME,
    ):
        self.__logging_level = logging_level
        self.__show_time = show_time
        self._input = DictToObject(input)
        self._args = args
        self._env = DictToObject(env)
        self._xcom = DictToObject(xcom)

    def __repr__(self):
        class_name = self.__class__.__name__
        input = self._input
        args = self._args
        env = self._env
        xcom = self._xcom
        return f"<{class_name} input={input} args={args} xcom={xcom} env={env}>"

    @property
    def input(self) -> DictToObject:
        return self._input

    @property
    def env(self) -> DictToObject:
        return self._env

    @property
    def args(self) -> list[Any]:
        return self._args

    @property
    def xcom(self) -> DictToObject:
        return self._xcom

    def get_logging_level(self) -> int:
        return self.__logging_level

    def should_show_time(self) -> bool:
        return self.__show_time

    def render(self, template: str) -> str:
        return fstring_like_format(
            template=template,
            data={
                "input": self._input,
                "args": self._args,
                "env": self._env,
                "xcom": self._xcom,
                "datetime": datetime,
            }
        )
