"""
LSP Manager - Singleton that manages LSP server instances.

Provides lazy initialization, auto-detection, and lifecycle management for LSP servers.
"""

import asyncio
import os
import weakref
from pathlib import Path
from typing import Optional, Any

from zrb.llm.lsp.protocol import (
    Diagnostic,
    DocumentSymbol,
    Location,
    SymbolInformation,
    SymbolKind,
)
from zrb.llm.lsp.server import (
    LSPServer,
    LSPServerConfig,
    LSP_SERVER_CONFIGS,
    detect_available_lsp_servers,
    get_lsp_config_for_file,
    detect_language_from_file,
)
from zrb.context.any_context import zrb_print


class LSPManager:
    """
    Singleton manager for LSP server instances.

    Features:
    - Lazy start (only start server when needed)
    - Auto-detect available LSP servers
    - One server instance per language per project root
    - Idle shutdown to free resources
    - Symbol-based API (more LLM-friendly than position-based)
    """

    _instance: Optional["LSPManager"] = None
    _servers: dict[str, LSPServer]   # key: "language:root_path"
    _lock: asyncio.Lock
    _project_roots: dict[str, str]  # file_path -> detected root
    _idle_tasks: dict[str, asyncio.Task]

    # Idle timeout in seconds (5 minutes)
    IDLE_TIMEOUT = 300

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._servers = {}
            cls._instance._lock = None  # Initialize lazily
            cls._instance._project_roots = {}
            cls._instance._idle_tasks = {}
        return cls._instance

    @property
    def lock(self) -> asyncio.Lock:
        """Get or create the asyncio lock."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def list_available_servers(self) -> dict[str, str]:
        """List all LSP servers detected on the system.

        Returns:
            Dict mapping server name to executable path.
        """
        return detect_available_lsp_servers()

    def detect_project_root(self, file_path: str) -> str:
        """Detect the project root for a file.

        Looks for common project markers:
        - .git (Git repository)
        - pyproject.toml, setup.py, setup.cfg (Python)
        - go.mod (Go)
        - Cargo.toml (Rust)
        - package.json (Node.js)
        - build.gradle, pom.xml (Java)
        - etc.
        """
        if file_path in self._project_roots:
            return self._project_roots[file_path]

        path = Path(file_path).resolve()
        if path.is_file():
            path = path.parent

        project_markers = [
            ".git",
            "pyproject.toml",
            "setup.py",
            "setup.cfg",
            "requirements.txt",
            "go.mod",
            "Cargo.toml",
            "package.json",
            "build.gradle",
            "pom.xml",
            "Gemfile",
            "composer.json",
            "*.csproj",
            "Makefile",
            "CMakeLists.txt",
        ]

        current = path
        while current != current.parent:
            for marker in project_markers:
                if marker.startswith("*"):
                    # Glob pattern
                    if list(current.glob(marker)):
                        self._project_roots[file_path] = str(current)
                        return str(current)
                else:
                    if (current / marker).exists():
                        self._project_roots[file_path] = str(current)
                        return str(current)
            current = current.parent

        # Fallback to the original file's directory
        self._project_roots[file_path] = str(path)
        return str(path)

    def _get_server_key(self, language: str, root_path: str) -> str:
        """Get the key for a server instance."""
        return f"{language}:{root_path}"

    async def get_server(
        self,
        file_path: str,
        preferred_servers: Optional[list[str]] = None,
    ) -> Optional[LSPServer]:
        """Get or create an LSP server for the given file.

        Args:
            file_path: Path to the file
            preferred_servers: Optional list of preferred server names

        Returns:
            LSPServer instance if available, None otherwise
        """
        config = get_lsp_config_for_file(file_path, preferred_servers)
        if config is None:
            return None

        root = self.detect_project_root(file_path)
        key = self._get_server_key(config.language_ids[0], root)

        async with self.lock:
            # Check if server exists and is alive
            if key in self._servers:
                server = self._servers[key]
                if server.is_alive:
                    return server
                else:
                    # Clean up dead server
                    del self._servers[key]

            # Start new server
            server = LSPServer(config, root)
            success = await server.start()
            if success:
                self._servers[key] = server
                return server

            return None

    async def shutdown_all(self):
        """Shutdown all LSP servers."""
        async with self.lock:
            for key, server in list(self._servers.items()):
                try:
                    await server.stop()
                except Exception:
                    pass
            self._servers.clear()
            self._project_roots.clear()

    async def shutdown_idle(self):
        """Shutdown servers that have been idle for too long."""
        # This could be extended with last-use tracking
        pass

    # --- High-Level Symbol-Based API ---

    async def find_definition(
        self,
        symbol_name: str,
        file_path: str,
        symbol_kind: Optional[str] = None,
    ) -> dict:
        """
        Find the definition of a symbol.

        Uses a combination of symbol search and position-based lookup
        to handle LLM's approximate position knowledge.

        Args:
            symbol_name: Name of the symbol to find
            file_path: Path to a file where the symbol is referenced (uses as context)
            symbol_kind: Optional hint about symbol type (class, function, variable, etc.)

        Returns:
            Dict with location information or error message.
        """
        server = await self.get_server(file_path)
        if server is None:
            return {
                "error": f"No LSP server available for file: {file_path}. "
                f"[SUGGESTION]: Install an LSP server for this language. "
                f"Available servers: {list(self.list_available_servers().keys())}"
            }

        # Try workspace symbols first (works without position)
        try:
            symbols = await server.workspace_symbols(symbol_name)
            if symbols:
                # Filter by kind if specified
                matched = []
                for sym in symbols:
                    sym_name = sym.get("name", "")
                    if sym_name == symbol_name:
                        if symbol_kind:
                            kind_name = SymbolKind.name_for_kind(sym.get("kind", 0))
                            if symbol_kind.lower() in kind_name:
                                matched.append(sym)
                        else:
                            matched.append(sym)

                if matched:
                    # Return the best match
                    best = matched[0]
                    location = best.get("location", {})
                    return {
                        "found": True,
                        "symbol": best.get("name"),
                        "kind": SymbolKind.name_for_kind(best.get("kind", 0)),
                        "uri": location.get("uri", ""),
                        "range": location.get("range", {}),
                        "container": best.get("containerName", ""),
                    }
        except Exception:
            pass

        return {
            "found": False,
            "error": f"Symbol '{symbol_name}' not found. "
            f"[SUGGESTION]: Try using Grep to search for 'def {symbol_name}' or 'class {symbol_name}'",
        }

    async def find_references(
        self,
        symbol_name: str,
        file_path: str,
        line: int = 0,
        character: int = 0,
        include_declaration: bool = True,
    ) -> dict:
        """
        Find all references to a symbol.

        Args:
            symbol_name: Name of the symbol (for context)
            file_path: Path to a file containing the symbol
            line: Line number (0-based) if known
            character: Character position if known
            include_declaration: Whether to include the declaration

        Returns:
            Dict with list of references or error message.
        """
        server = await self.get_server(file_path)
        if server is None:
            return {
                "error": f"No LSP server available for file: {file_path}. "
                f"Available servers: {list(self.list_available_servers().keys())}"
            }

        try:
            # Read file to find symbol position if not provided
            if line == 0 and character == 0:
                position = await self._find_symbol_position(file_path, symbol_name)
                if position:
                    line, character = position

            refs = await server.find_references(file_path, line, character, include_declaration)
            if refs:
                locations = []
                for ref in refs:
                    uri = ref.get("uri", "")
                    range_info = ref.get("range", {})
                    locations.append({
                        "uri": uri,
                        "path": self._uri_to_path(uri),
                        "line": range_info.get("start", {}).get("line", 0) + 1,
                        "character": range_info.get("start", {}).get("character", 0),
                    })
                return {
                    "found": True,
                    "symbol": symbol_name,
                    "count": len(locations),
                    "references": locations,
                }
        except Exception as e:
            pass

        return {
            "found": False,
            "error": f"No references found for '{symbol_name}'. "
            f"[SUGGESTION]: Try using Grep to search for the symbol name.",
        }

    async def get_diagnostics(
        self,
        file_path: str,
        severity: Optional[str] = None,
    ) -> dict:
        """
        Get diagnostics (errors, warnings) for a file.

        Args:
            file_path: Path to the file
            severity: Filter by severity ("error", "warning", "info", "hint")

        Returns:
            Dict with list of diagnostics.
        """
        server = await self.get_server(file_path)
        if server is None:
            return {
                "error": f"No LSP server available for file: {file_path}. "
                f"Available servers: {list(self.list_available_servers().keys())}"
            }

        try:
            diagnostics = await server.get_diagnostics(file_path)
            if diagnostics:
                severity_map = {"error": 1, "warning": 2, "info": 3, "hint": 4}
                severity_filter = severity_map.get(severity.lower()) if severity else None

                results = []
                for diag in diagnostics:
                    diag_severity = diag.get("severity", 1)
                    if severity_filter and diag_severity != severity_filter:
                        continue

                    range_info = diag.get("range", {})
                    results.append({
                        "severity": ["error", "warning", "info", "hint"][diag_severity - 1]
                        if 1 <= diag_severity <= 4
                        else "unknown",
                        "message": diag.get("message", ""),
                        "line": range_info.get("start", {}).get("line", 0) + 1,
                        "character": range_info.get("start", {}).get("character", 0),
                        "source": diag.get("source", ""),
                        "code": diag.get("code"),
                    })

                return {
                    "found": True,
                    "file": file_path,
                    "count": len(results),
                    "diagnostics": results,
                }
        except Exception:
            pass

        return {
            "found": False,
            "file": file_path,
            "count": 0,
            "diagnostics": [],
            "message": "No diagnostics available. This may be normal for files without errors.",
        }

    async def get_document_symbols(self, file_path: str) -> dict:
        """
        Get all symbols defined in a document.

        Args:
            file_path: Path to the file

        Returns:
            Dict with list of symbols (classes, functions, variables, etc.).
        """
        server = await self.get_server(file_path)
        if server is None:
            return {
                "error": f"No LSP server available for file: {file_path}. "
                f"Available servers: {list(self.list_available_servers().keys())}"
            }

        try:
            symbols = await server.document_symbols(file_path)
            if symbols:
                results = self._format_document_symbols(symbols)
                return {
                    "found": True,
                    "file": file_path,
                    "count": len(results),
                    "symbols": results,
                }
        except Exception:
            pass

        return {
            "found": False,
            "error": "Could not retrieve document symbols. "
            "[SUGGESTION]: Ensure the LSP server supports this file type.",
        }

    async def get_workspace_symbols(self, query: str, file_path: str) -> dict:
        """
        Search for symbols across the workspace.

        Args:
            query: Symbol name or pattern to search for
            file_path: Path to a file in the project (for context)

        Returns:
            Dict with list of matching symbols.
        """
        server = await self.get_server(file_path)
        if server is None:
            return {
                "error": f"No LSP server available for file: {file_path}. "
                f"Available servers: {list(self.list_available_servers().keys())}"
            }

        try:
            symbols = await server.workspace_symbols(query)
            if symbols:
                results = []
                for sym in symbols[:50]:  # Limit to 50 results
                    location = sym.get("location", {})
                    results.append({
                        "name": sym.get("name", ""),
                        "kind": SymbolKind.name_for_kind(sym.get("kind", 0)),
                        "uri": location.get("uri", ""),
                        "path": self._uri_to_path(location.get("uri", "")),
                        "container": sym.get("containerName", ""),
                    })
                return {
                    "found": True,
                    "query": query,
                    "count": len(results),
                    "symbols": results,
                }
        except Exception:
            pass

        return {
            "found": False,
            "error": f"No symbols found matching '{query}'.",
        }

    async def get_hover_info(
        self,
        file_path: str,
        line: int,
        character: int,
    ) -> dict:
        """
        Get hover information (type, docs) at a position.

        Args:
            file_path: Path to the file
            line: Line number (0-based)
            character: Character position

        Returns:
            Dict with hover information.
        """
        server = await self.get_server(file_path)
        if server is None:
            return {
                "error": f"No LSP server available for file: {file_path}. "
                f"Available servers: {list(self.list_available_servers().keys())}"
            }

        try:
            hover = await server.hover(file_path, line, character)
            if hover:
                content = hover.get("contents", "")
                if isinstance(content, dict):
                    content = content.get("value", str(content))
                elif isinstance(content, list):
                    content = "\n".join(
                        c.get("value", str(c)) if isinstance(c, dict) else str(c)
                        for c in content
                    )

                return {
                    "found": True,
                    "file": file_path,
                    "line": line + 1,
                    "character": character,
                    "info": content.strip(),
                }
        except Exception:
            pass

        return {
            "found": False,
            "error": "No hover information available at this position.",
        }

    async def rename_symbol(
        self,
        symbol_name: str,
        new_name: str,
        file_path: str,
        line: int = 0,
        character: int = 0,
        dry_run: bool = True,
    ) -> dict:
        """
        Rename a symbol across the workspace.

        Args:
            symbol_name: Current name of the symbol (for context)
            new_name: New name for the symbol
            file_path: Path to a file containing the symbol
            line: Line number if known
            character: Character position if known
            dry_run: If True, only preview changes without applying

        Returns:
            Dict with rename preview or result.
        """
        server = await self.get_server(file_path)
        if server is None:
            return {
                "error": f"No LSP server available for file: {file_path}. "
                f"Available servers: {list(self.list_available_servers().keys())}"
            }

        try:
            # Find symbol position if not provided
            if line == 0 and character == 0:
                position = await self._find_symbol_position(file_path, symbol_name)
                if position:
                    line, character = position

            result = await server.rename(file_path, line, character, new_name, dry_run=dry_run)
            if result:
                changes = result.get("documentChanges") or result.get("changes", {})
                total_edits = 0
                files_affected = []

                # Handle different change formats
                for uri, edits in changes.items():
                    if isinstance(edits, list):
                        total_edits += len(edits)
                        files_affected.append(self._uri_to_path(uri))

                return {
                    "success": True,
                    "symbol": symbol_name,
                    "new_name": new_name,
                    "dry_run": dry_run,
                    "files_affected": len(files_affected),
                    "total_edits": total_edits,
                    "changes": changes if dry_run else "Applied",
                }
        except Exception as e:
            pass

        return {
            "success": False,
            "error": f"Could not rename symbol '{symbol_name}'. "
            f"[SUGGESTION]: Try using Grep to find all occurrences and Edit to change them.",
        }

    # --- Helper Methods ---

    def _uri_to_path(self, uri: str) -> str:
        """Convert file URI to path."""
        if uri.startswith("file://"):
            from urllib.parse import unquote, urlparse
            return unquote(urlparse(uri).path)
        return uri

    async def _find_symbol_position(
        self, file_path: str, symbol_name: str
    ) -> Optional[tuple[int, int]]:
        """Find the position of a symbol in a file using document symbols."""
        try:
            symbols = await self.get_document_symbols(file_path)
            if symbols.get("found"):
                for sym in symbols.get("symbols", []):
                    if sym.get("name") == symbol_name:
                        return (sym.get("line", 1) - 1, sym.get("character", 0))
                    # Check nested symbols
                    for child in sym.get("children", []):
                        if child.get("name") == symbol_name:
                            return (child.get("line", 1) - 1, child.get("character", 0))
        except Exception:
            pass

        # Fallback: Grep for the symbol
        try:
            import re
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for i, line in enumerate(f):
                    # Try various patterns
                    patterns = [
                        rf"^(def|class|func|fn|fn|function|const|let|var)\s+{re.escape(symbol_name)}\b",
                        rf"\b{re.escape(symbol_name)}\s*=",
                        rf"\b{re.escape(symbol_name)}\b",
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, line)
                        if match:
                            return (i, match.start())
        except Exception:
            pass

        return None

    def _format_document_symbols(self, symbols: list, depth: int = 0) -> list[dict]:
        """Format document symbols into a flat list with hierarchy info."""
        results = []
        for sym in symbols:
            if isinstance(sym, dict):
                name = sym.get("name", "")
                kind = sym.get("kind", 0)
                range_info = sym.get("range", {})
                selection_range = sym.get("selectionRange", {})
                detail = sym.get("detail", "")

                results.append({
                    "name": name,
                    "kind": SymbolKind.name_for_kind(kind),
                    "line": selection_range.get("start", {}).get("line", 0) + 1,
                    "end_line": range_info.get("end", {}).get("line", 0) + 1,
                    "character": selection_range.get("start", {}).get("character", 0),
                    "detail": detail,
                    "depth": depth,
                })

                # Recursively format children
                children = sym.get("children", [])
                if children:
                    results.extend(self._format_document_symbols(children, depth + 1))

        return results


# Singleton instance
lsp_manager = LSPManager()