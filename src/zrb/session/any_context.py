from abc import ABC, abstractmethod
from typing import Any, TextIO
from collections.abc import Mapping

import sys


class AnyContext(ABC):
    @abstractmethod
    def set_attempt(self, attempt: int):
        pass

    @abstractmethod
    def set_max_attempt(self, max_attempt: int):
        pass

    @abstractmethod
    def render(self, template: str, additional_data: Mapping[str, Any] = {}):
        pass

    @abstractmethod
    def print(
        self,
        *values: object,
        sep: str | None = " ",
        end: str | None = "\n",
        file: TextIO | None = sys.stderr,
        flush: bool = True
    ):
        pass
