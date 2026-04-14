"""
LSP Tools for zrb LLM integration.

These tools provide IDE-like code intelligence capabilities to the LLM assistant.
"""

import asyncio
from typing import Literal

from zrb.llm.lsp.manager import lsp_manager


async def find_definition(
    symbol_name: str,
    file_path: str,
    symbol_kind: str = "",
) -> dict:
    """
    Find where a symbol (class, function, variable) is defined.

    Uses LSP (Language Server Protocol) for semantic code navigation.
    More precise than text search - understands code structure.

    MANDATES:
    - Use when you need to locate the definition of a symbol.
    - Works best for code symbols (classes, functions, methods, variables).
    - Symbol kind hints: "class", "function", "method", "variable", "constant".
    - Returns the file path, line number, and context.
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
    Find all references to a symbol across the codebase.

    Uses LSP for semantic reference finding - understands imports, aliases, etc.
    More accurate than grep for finding all usages of a symbol.

    MANDATES:
    - Use when you need to understand where/how a symbol is used.
    - Great for impact analysis before refactoring.
    - If line/character are unknown, pass 0 - the tool will attempt to find it.
    """
    return await lsp_manager.find_references(
        symbol_name, file_path, line, character, include_declaration
    )


async def get_diagnostics(
    file_path: str,
    severity: Literal["error", "warning", "info", "hint"] | None = None,
) -> dict:
    """
    Get diagnostics (errors, warnings, hints) for a file.

    Uses LSP to get real-time type checking, linting results, etc.
    Essential for verifying code correctness after edits.

    MANDATES:
    - Use to check for type errors, syntax errors, linting issues.
    - Use after making edits to verify the code is still valid.
    - Severity can filter: "error", "warning", "info", "hint".
    """
    return await lsp_manager.get_diagnostics(file_path, severity)


async def get_document_symbols(file_path: str) -> dict:
    """
    Get all symbols (classes, functions, variables) defined in a file.

    Uses LSP to parse and understand the file structure.
    Great for getting an overview without reading the entire file.

    MANDATES:
    - Use for quick file overview without reading full content.
    - Shows class hierarchy, function signatures, imports, etc.
    - Much faster than reading and parsing the file manually.
    """
    return await lsp_manager.get_document_symbols(file_path)


async def get_workspace_symbols(
    query: str,
    file_path: str = ".",
) -> dict:
    """
    Search for symbols across the entire workspace/project.

    Uses LSP workspace symbols for fast symbol search.
    Like "Go to Symbol in Workspace" in IDEs.

    MANDATES:
    - Use when you know a symbol name but not which file it's in.
    - Query can be partial - supports fuzzy matching.
    - file_path provides project context (can be any file in project).
    """
    return await lsp_manager.get_workspace_symbols(query, file_path)


async def get_hover_info(
    file_path: str,
    line: int,
    character: int,
) -> dict:
    """
    Get hover information (type, documentation) at a position.

    Uses LSP hover capability - like hovering over code in an IDE.
    Shows type information, function signatures, docstrings.

    MANDATES:
    - Use to understand the type of a variable or expression.
    - Use to see function signatures and parameters.
    - Line and character are 0-based indices.
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
    Rename a symbol across all files in the workspace.

    Uses LSP rename capability for safe refactoring.
    Understands imports, aliases, and cross-file references.

    MANDATES:
    - Use dry_run=True (default) to preview changes before applying.
    - Use instead of Edit for symbol renaming (catches all references).
    - Works for variables, functions, classes, methods, etc.
    - If line/character are unknown, pass 0 for auto-detection.
    """
    return await lsp_manager.rename_symbol(
        symbol_name, new_name, file_path, line, character, dry_run
    )


async def list_available_servers() -> dict:
    """
    List all LSP servers detected on the system.

    Shows which languages are supported for LSP-based code intelligence.
    Use this to diagnose why LSP tools might not be working for a language.

    MANDATES:
    - Use to check if LSP servers are installed.
    - Helpful for debugging "No LSP server available" errors.
    - Install missing LSP servers to enable semantic code intelligence.
    """
    servers = lsp_manager.list_available_servers()
    language_support = {}
    for name, path in servers.items():
        from zrb.llm.lsp.server import LSP_SERVER_CONFIGS

        config = LSP_SERVER_CONFIGS.get(name)
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


# Set function names for tool display
find_definition.__name__ = "LspFindDefinition"
find_references.__name__ = "LspFindReferences"
get_diagnostics.__name__ = "LspGetDiagnostics"
get_document_symbols.__name__ = "LspGetDocumentSymbols"
get_workspace_symbols.__name__ = "LspGetWorkspaceSymbols"
get_hover_info.__name__ = "LspGetHoverInfo"
rename_symbol.__name__ = "LspRenameSymbol"
list_available_servers.__name__ = "LspListServers"


# Tool creation functions for integration with chat.py
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
