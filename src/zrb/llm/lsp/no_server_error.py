"""Helper for the repeated 'no LSP server available' error shape.

Eight `LSPManager` query methods all return the same dict when no server
is available; this helper centralizes the shape so changes to the message
or installation hint stay in one place.
"""

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
