from typing import Any
from .any_shared_context import AnySharedContext
from ..dot_dict.dot_dict import DotDict
from ..xcom.xcom import Xcom
from ..config import LOGGING_LEVEL
from ..session.any_session import AnySession
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
    ):
        self.__logging_level = logging_level
        self._input = DotDict(input)
        self._args = args
        self._env = DotDict(env)
        self._xcom = DotDict(xcom)
        self._session: AnySession | None = None
        self._final_result = None
        self._log = []

    def __repr__(self):
        class_name = self.__class__.__name__
        final_result = self._final_result
        input = self._input
        args = self._args
        env = self._env
        xcom = self._xcom
        return f"<{class_name} final_result={final_result} input={input} args={args} xcom={xcom} env={env}>"  # noqa

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

    @property
    def shared_log(self) -> list[str]:
        return self._log

    @property
    def final_result(self) -> Any:
        return self._final_result

    @property
    def session(self) -> AnySession | None:
        return self._session

    def set_session(self, session: AnySession):
        self._session = session

    def set_final_result(self, final_result: Any):
        self._final_result = final_result

    def get_logging_level(self) -> int:
        return self.__logging_level

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
