"""LSP code-intelligence tools for the LLM agent."""

from typing import Literal

from zrb.llm.lsp.configs import lsp_server_configs
from zrb.llm.lsp.manager import lsp_manager


async def find_definition(
    symbol_name: str,
    file_path: str,
    symbol_kind: str = "",
) -> dict:
    """
    Find where a symbol (class, function, variable) is defined, via LSP.
    """
    return await lsp_manager.find_definition(
        symbol_name, file_path, symbol_kind or None
    )


async def find_references(
    symbol_name: str,
    file_path: str,
    line: int = 0,
    character: int = 0,
    include_declaration: bool = True,
) -> dict:
    """
    Find all references to a symbol across the codebase, via LSP (follows
    imports and aliases, unlike grep). Pass 0 for unknown line/character.
    """
    return await lsp_manager.find_references(
        symbol_name, file_path, line, character, include_declaration
    )


async def get_diagnostics(
    file_path: str,
    severity: Literal["error", "warning", "info", "hint"] | None = None,
) -> dict:
    """
    Get LSP diagnostics (type-check and lint results) for a file; use to
    verify code after edits.
    """
    return await lsp_manager.get_diagnostics(file_path, severity)


async def get_document_symbols(file_path: str) -> dict:
    """
    Get all symbols (classes, functions, variables) defined in a file, as an
    overview without reading it.
    """
    return await lsp_manager.get_document_symbols(file_path)


async def get_workspace_symbols(
    query: str,
    file_path: str = ".",
) -> dict:
    """
    Search for symbols across the workspace, via LSP. Query may be partial
    (fuzzy).
    """
    return await lsp_manager.get_workspace_symbols(query, file_path)


async def get_hover_info(
    file_path: str,
    line: int,
    character: int,
) -> dict:
    """
    Get hover information (type, signature, docstring) at a position. Line and
    character are 0-based.
    """
    return await lsp_manager.get_hover_info(file_path, line, character)


async def rename_symbol(
    symbol_name: str,
    new_name: str,
    file_path: str,
    line: int = 0,
    character: int = 0,
    dry_run: bool = True,
) -> dict:
    """
    Rename a symbol across all files via LSP; prefer over Edit for renames
    (catches all references). `dry_run=True` (default) previews without
    applying. Pass 0 for unknown line/character.
    """
    return await lsp_manager.rename_symbol(
        symbol_name, new_name, file_path, line, character, dry_run
    )


async def list_available_servers() -> dict:
    """
    List detected LSP servers and supported languages; use to diagnose why LSP
    tools fail for a language.
    """
    servers = lsp_manager.list_available_servers()
    language_support = {}
    for name, path in servers.items():

        config = lsp_server_configs.get(name)
        if config:
            for lang in config.language_ids:
                if lang not in language_support:
                    language_support[lang] = []
                language_support[lang].append(name)

    return {
        "servers": servers,
        "language_support": language_support,
        "message": f"Found {len(servers)} LSP server(s) installed.",
        "suggestion": "Install LSP servers for unsupported languages: "
        "pyright/pylsp (Python), gopls (Go), typescript-language-server (TypeScript), "
        "rust-analyzer (Rust), clangd (C/C++), etc.",
    }


find_definition.__name__ = "LspFindDefinition"
find_references.__name__ = "LspFindReferences"
get_diagnostics.__name__ = "LspGetDiagnostics"
get_document_symbols.__name__ = "LspGetDocumentSymbols"
get_workspace_symbols.__name__ = "LspGetWorkspaceSymbols"
get_hover_info.__name__ = "LspGetHoverInfo"
rename_symbol.__name__ = "LspRenameSymbol"
list_available_servers.__name__ = "LspListServers"


def create_lsp_tools() -> list:
    """Create LSP tool functions for registration with LLMChatTask."""
    return [
        find_definition,
        find_references,
        get_diagnostics,
        get_document_symbols,
        get_workspace_symbols,
        get_hover_info,
        rename_symbol,
        list_available_servers,
    ]
