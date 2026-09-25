"""The shared 'no LSP server available' result every LSP query returns."""

from __future__ import annotations

from typing import Callable


def no_server_error(
    file_path: str,
    list_available_servers: Callable[[], dict[str, str]],
    *,
    success_key: str = "found",
    extra_hint: str | None = None,
) -> dict:
    """Build the standard 'no LSP server available' result.

    `success_key` is "found" for query methods and "success" for `rename_symbol`.
    `extra_hint` is the install-an-LSP-server suggestion shown by `find_definition`.
    """
    available = list(list_available_servers().keys())
    error = f"No LSP server available for file: {file_path}. "
    if extra_hint:
        error += f"{extra_hint} "
    error += f"Available servers: {available}"
    return {success_key: False, "error": error}
