"""The process-wide owner of the running LSP servers.

`LSPManager` starts one server per language per project root and sends each
query to the one that answers for it; `lsp_manager` is the instance every
caller shares. The other modules here hold its parts — lifecycle and queries —
and the names below are the public surface, unchanged from the module this
replaced.
"""

from zrb.llm.lsp.manager.manager import LSPManager, lsp_manager

__all__ = [
    "LSPManager",
    "lsp_manager",
]
