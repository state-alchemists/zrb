"""
LSP (Language Server Protocol) integration for zrb.

Provides IDE-like code intelligence capabilities:
- Go to definition
- Find references
- Get diagnostics
- Document symbols
- Rename symbols
"""

from zrb.llm.lsp.manager import lsp_manager
from zrb.llm.lsp.tools import (
    find_definition,
    find_references,
    get_diagnostics,
    get_document_symbols,
    get_hover_info,
    get_workspace_symbols,
    list_available_servers,
    rename_symbol,
)

__all__ = [
    "lsp_manager",
    "find_definition",
    "find_references",
    "get_diagnostics",
    "get_document_symbols",
    "get_workspace_symbols",
    "rename_symbol",
    "get_hover_info",
    "list_available_servers",
]
