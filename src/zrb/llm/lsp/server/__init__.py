"""One language-server subprocess: JSON-RPC over stdio, handshake, stop.

`LSPServer` drives the subprocess and `LSPServerConfig` describes one. The other
modules here hold its parts — the operations it answers — and the names below
are the public surface, unchanged from the module this replaced.
"""

from .server import (
    LSP_SERVER_CONFIGS,
    LSPServer,
    LSPServerConfig,
    detect_available_lsp_servers,
    detect_language_from_file,
    get_lsp_config_for_file,
    lsp_server_configs,
)

__all__ = [
    "LSP_SERVER_CONFIGS",
    "LSPServer",
    "LSPServerConfig",
    "detect_available_lsp_servers",
    "detect_language_from_file",
    "get_lsp_config_for_file",
    "lsp_server_configs",
]
