import datetime
import sys
from typing import Any

from zrb.config.config import CFG
from zrb.context.any_shared_context import AnySharedContext
from zrb.dot_dict.dot_dict import DotDict
from zrb.session.any_session import AnySession
from zrb.util.string.conversion import (
    double_quote,
    to_boolean,
    to_camel_case,
    to_human_case,
    to_kebab_case,
    to_pascal_case,
    to_snake_case,
)
from zrb.util.string.format import fstring_format
from zrb.xcom.xcom import Xcom


class SharedContext(AnySharedContext):
    def __init__(
        self,
        input: dict[str, Any] = {},
        args: list[Any] = [],
        env: dict[str, str] = {},
        xcom: dict[str, Xcom] = {},
        logging_level: int | None = None,
        is_web_mode: bool = False,
    ):
        self.__logging_level = logging_level
        self._input = DotDict(input)
        self._args = args
        self._env = DotDict(env)
        self._xcom = DotDict(xcom)
        self._session: AnySession | None = None
        self._log = []
        self._is_web_mode = is_web_mode

    def __repr__(self):
        class_name = self.__class__.__name__
        return f"<{class_name}>"

    @property
    def is_web_mode(self) -> bool:
        return self._is_web_mode

    @property
    def is_tty(self) -> bool:
        try:
            return sys.stdin.isatty()
        except Exception:
            return False

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
    def session(self) -> AnySession | None:
        return self._session

    def append_to_shared_log(self, message: str):
        self._log.append(message)
        session = self.session
        if session is not None:
            session_parent: AnySession = session.parent
            if session_parent is not None:
                session_parent.shared_ctx.append_to_shared_log(message)

    def set_session(self, session: AnySession):
        self._session = session

    def get_logging_level(self) -> int:
        if self.__logging_level is None:
            return CFG.LOGGING_LEVEL
        return self.__logging_level

    def render(self, template: str) -> str:
        return fstring_format(
            template=template,
            data={
                "ctx": self,
                "datetime": datetime,
                "to_boolean": to_boolean,
                "to_camel_case": to_camel_case,
                "to_human_case": to_human_case,
                "to_kebab_case": to_kebab_case,
                "to_pascal_case": to_pascal_case,
                "to_snake_case": to_snake_case,
                "double_quote": double_quote,
            },
        )
