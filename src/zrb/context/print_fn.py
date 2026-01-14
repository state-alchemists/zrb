from typing import Protocol, TextIO


class PrintFn(Protocol):
    def __call__(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
    ) -> None:
        pass
