"""
LSP Tools for zrb LLM integration.

These tools provide IDE-like code intelligence capabilities to the LLM assistant.
"""

import asyncio
from typing import Literal, Optional

from zrb.llm.lsp.manager import lsp_manager


async def find_definition(
    symbol_name: str,
    file_path: str,
    symbol_kind: Optional[str] = None,
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

    Args:
        symbol_name: Name of the symbol to find (e.g., "LLMChatTask", "process_data")
        file_path: Path to any file in the project for context (used to detect project root)
        symbol_kind: Optional hint about symbol type ("class", "function", etc.)

    Returns:
        Dict with location information or error message.
    """
    return await lsp_manager.find_definition(symbol_name, file_path, symbol_kind)


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

    Args:
        symbol_name: Name of the symbol to find references for
        file_path: Path to a file where the symbol is defined or used
        line: Line number if known (0-based, default 0 for auto-detect)
        character: Character position if known (0-based)
        include_declaration: Whether to include the symbol's declaration

    Returns:
        Dict with list of references (file, line, character) or error message.
    """
    return await lsp_manager.find_references(
        symbol_name, file_path, line, character, include_declaration
    )


async def get_diagnostics(
    file_path: str,
    severity: Optional[Literal["error", "warning", "info", "hint"]] = None,
) -> dict:
    """
    Get diagnostics (errors, warnings, hints) for a file.

    Uses LSP to get real-time type checking, linting results, etc.
    Essential for verifying code correctness after edits.

    MANDATES:
    - Use to check for type errors, syntax errors, linting issues.
    - Use after making edits to verify the code is still valid.
    - Severity can filter: "error", "warning", "info", "hint".

    Args:
        file_path: Path to the file to check
        severity: Optional filter by severity level

    Returns:
        Dict with list of diagnostics or empty list if no issues.
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

    Args:
        file_path: Path to the file to analyze

    Returns:
        Dict with list of symbols (name, kind, line, etc.) or error message.
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

    Args:
        query: Symbol name or pattern to search for (supports partial matching)
        file_path: Path to any file in the project for context (default: ".")

    Returns:
        Dict with list of matching symbols or error message.
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

    Args:
        file_path: Path to the file
        line: Line number (0-based)
        character: Character position in the line (0-based)

    Returns:
        Dict with hover information or error message.
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

    Args:
        symbol_name: Current name of the symbol (for context)
        new_name: New name for the symbol
        file_path: Path to a file containing the symbol
        line: Line number if known (0-based, default 0 for auto-detect)
        character: Character position if known (0-based)
        dry_run: If True, preview changes without applying (default: True)

    Returns:
        Dict with rename preview or result.
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

    Returns:
        Dict mapping server names to their installation paths.
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
        "rust-analyzer (Rust), clangd (C/C++), etc."
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