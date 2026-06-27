"""
Custom LSP Server Example

Registers LSP servers that aren't in zrb's built-in catalogue (Zig and Nim),
plus an override that re-points an existing name to a different binary. After
registration, the new servers behave exactly like the built-ins: auto-detection
via PATH, file-extension matching, and `ZRB_LLM_LSP_PREFERRED_SERVERS` ordering.

The LLM's LSP tools (LspFindDefinition, LspGetDocumentSymbols, LspListServers,
...) will use these servers whenever it touches a matching file — no other
wiring needed.

Usage:
    cd examples/lsp-config
    zrb llm chat
    > What LSP servers are available?      # registered ones show up if installed
    > Show me all symbols in main.zig
"""

from zrb.llm.lsp.configs import LSPServerConfig
from zrb.llm.lsp.manager import lsp_manager

# =============================================================================
# Add a language the built-in catalogue doesn't cover: Zig (zls).
# =============================================================================

lsp_manager.register_lsp_server(
    "zls",
    LSPServerConfig(
        name="zls",
        command=["zls"],  # must be on PATH for auto-detection
        language_ids=["zig"],
        file_extensions=[".zig"],
    ),
)

# =============================================================================
# Another missing language: Nim (nimlangserver).
# =============================================================================

lsp_manager.register_lsp_server(
    "nimlangserver",
    LSPServerConfig(
        name="nimlangserver",
        command=["nimlangserver"],
        language_ids=["nim"],
        file_extensions=[".nim", ".nims"],
    ),
)

# =============================================================================
# Override a built-in: force a custom Python LSP binary under the "pyright"
# name. Registering an existing name replaces the built-in config for it.
# =============================================================================

lsp_manager.register_lsp_server(
    "pyright",
    LSPServerConfig(
        name="pyright",
        command=["pyright-langserver", "--stdio"],
        language_ids=["python"],
        file_extensions=[".py", ".pyi", ".pyw"],
    ),
)
