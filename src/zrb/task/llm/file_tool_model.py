import sys
from typing import Literal

if sys.version_info >= (3, 12):
    from typing import NotRequired, TypedDict
else:
    from typing_extensions import NotRequired, TypedDict


class FileToRead(TypedDict):
    """
    Configuration for reading a file or file section.

    Attributes:
        path (str): Absolute or relative path to the file
        start_line (int | None): Starting line number (1-based, inclusive).
            If None, reads from beginning.
        end_line (int | None): Ending line number (1-based, exclusive). If None, reads to end.
    """

    path: str
    start_line: NotRequired[int | None]
    end_line: NotRequired[int | None]


class FileToWrite(TypedDict):
    """
    Configuration for writing content to a file.

    Attributes:
        path (str): Absolute or relative path where file will be written.
        content (str): Content to write. CRITICAL: For JSON, ensure all special characters
            in this string are properly escaped.
        mode (str): Mode for writing:
            'w' (overwrite, default), 'a' (append), 'x' (create exclusively).
    """

    path: str
    content: str
    mode: NotRequired[Literal["w", "wt", "tw", "a", "at", "ta", "x", "xt", "tx"]]


class FileReplacement(TypedDict):
    """
    Configuration for a single text replacement operation in a file.

    Attributes:
        path (str): Absolute or relative path to the file
        old_text (str): Exact text to find and replace (must match file content exactly)
        new_text (str): New text to replace with
        count (int): Optional. Number of occurrences to replace. Defaults to -1 (all).
    """

    path: str
    old_text: str
    new_text: str
    count: NotRequired[int]
