"""High-level symbol-based LSP queries for `LSPManager`.

Each method routes through `self.get_server(...)` (provided by the
lifecycle mixin) and returns a friendly dict with a `found`/`success`
flag. The `_find_symbol_position` helper bridges symbol names to
`(line, character)` for callers that don't have the position handy.
"""

from __future__ import annotations

import re

from zrb.llm.lsp.manager.symbol_utils import format_document_symbols, uri_to_path
from zrb.llm.lsp.no_server_error import no_server_error
from zrb.llm.lsp.protocol import SymbolKind


class QueryMixin:
    """LSP query methods exposed on `LSPManager`."""

    async def find_definition(
        self,
        symbol_name: str,
        file_path: str,
        symbol_kind: str | None = None,
    ) -> dict:
        """Find the definition of a symbol.

        Combines workspace symbol search with kind filtering to handle the LLM's
        approximate position knowledge.
        """
        server = await self.get_server(file_path)
        if server is None:
            return no_server_error(
                file_path,
                self.list_available_servers,
                extra_hint="[SUGGESTION]: Install an LSP server for this language.",
            )

        # Primary path: textDocument/definition at an occurrence of the symbol in
        # `file_path`. This is how editors implement "go to definition" and works
        # on every LSP server. The previous workspace/symbol-only approach failed
        # on pyright (returns nothing without indexing) and pylsp (doesn't
        # implement workspace/symbol at all).
        try:
            position = await self._find_symbol_position(file_path, symbol_name)
            if position:
                line, character = position
                locations = await server.goto_definition(file_path, line, character)
                if locations:
                    loc = locations[0]
                    # Location uses uri/range; LocationLink uses target*.
                    uri = loc.get("uri") or loc.get("targetUri", "")
                    rng = loc.get("range") or loc.get("targetRange", {})
                    return {
                        "found": True,
                        "symbol": symbol_name,
                        "uri": uri,
                        "path": uri_to_path(uri),
                        "range": rng,
                    }
        except Exception:
            pass

        # Fallback: workspace symbol search, for servers that support it well
        # (gopls, rust-analyzer, typescript-language-server, clangd, jdtls).
        try:
            symbols = await server.workspace_symbols(symbol_name)
            if symbols:
                matched = []
                for sym in symbols:
                    if sym.get("name", "") != symbol_name:
                        continue
                    if symbol_kind:
                        kind_name = SymbolKind.name_for_kind(sym.get("kind", 0))
                        if symbol_kind.lower() in kind_name:
                            matched.append(sym)
                    else:
                        matched.append(sym)

                if matched:
                    best = matched[0]
                    location = best.get("location", {})
                    return {
                        "found": True,
                        "symbol": best.get("name"),
                        "kind": SymbolKind.name_for_kind(best.get("kind", 0)),
                        "uri": location.get("uri", ""),
                        "path": uri_to_path(location.get("uri", "")),
                        "range": location.get("range", {}),
                        "container": best.get("containerName", ""),
                    }
        except Exception:
            pass

        return {
            "found": False,
            "error": (
                f"Symbol '{symbol_name}' not found. [SUGGESTION]: Try using "
                f"Grep to search for 'def {symbol_name}' or 'class {symbol_name}'"
            ),
        }

    async def find_references(
        self,
        symbol_name: str,
        file_path: str,
        line: int = 0,
        character: int = 0,
        include_declaration: bool = True,
    ) -> dict:
        """Find all references to a symbol. Falls back to grep if position unknown."""
        server = await self.get_server(file_path)
        if server is None:
            return no_server_error(file_path, self.list_available_servers)

        try:
            if line == 0 and character == 0:
                position = await self._find_symbol_position(file_path, symbol_name)
                if position:
                    line, character = position

            refs = await server.find_references(
                file_path, line, character, include_declaration
            )
            if refs:
                locations = []
                for ref in refs:
                    uri = ref.get("uri", "")
                    range_info = ref.get("range", {})
                    locations.append(
                        {
                            "uri": uri,
                            "path": uri_to_path(uri),
                            "line": range_info.get("start", {}).get("line", 0) + 1,
                            "character": range_info.get("start", {}).get(
                                "character", 0
                            ),
                        }
                    )
                return {
                    "found": True,
                    "symbol": symbol_name,
                    "count": len(locations),
                    "references": locations,
                }
        except Exception:
            pass

        return {
            "found": False,
            "error": (
                f"No references found for '{symbol_name}'. "
                f"[SUGGESTION]: Try using Grep to search for the symbol name."
            ),
        }

    async def get_diagnostics(
        self,
        file_path: str,
        severity: str | None = None,
    ) -> dict:
        """Get diagnostics (errors, warnings) for a file."""
        server = await self.get_server(file_path)
        if server is None:
            return no_server_error(file_path, self.list_available_servers)

        try:
            diagnostics = await server.get_diagnostics(file_path)
            if diagnostics:
                severity_map = {"error": 1, "warning": 2, "info": 3, "hint": 4}
                severity_filter = (
                    severity_map.get(severity.lower()) if severity else None
                )

                results = []
                for diag in diagnostics:
                    diag_severity = diag.get("severity", 1)
                    if severity_filter and diag_severity != severity_filter:
                        continue

                    range_info = diag.get("range", {})
                    results.append(
                        {
                            "severity": (
                                ["error", "warning", "info", "hint"][diag_severity - 1]
                                if 1 <= diag_severity <= 4
                                else "unknown"
                            ),
                            "message": diag.get("message", ""),
                            "line": range_info.get("start", {}).get("line", 0) + 1,
                            "character": range_info.get("start", {}).get(
                                "character", 0
                            ),
                            "source": diag.get("source", ""),
                            "code": diag.get("code"),
                        }
                    )

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
            "message": (
                "No diagnostics available. This may be normal for files without errors."
            ),
        }

    async def get_document_symbols(self, file_path: str) -> dict:
        """Get all symbols (classes, functions, variables) defined in a document."""
        server = await self.get_server(file_path)
        if server is None:
            return no_server_error(file_path, self.list_available_servers)

        try:
            symbols = await server.document_symbols(file_path)
            if symbols:
                results = format_document_symbols(symbols)
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
            "error": (
                "Could not retrieve document symbols. "
                "[SUGGESTION]: Ensure the LSP server supports this file type."
            ),
        }

    async def get_workspace_symbols(self, query: str, file_path: str) -> dict:
        """Search for symbols across the workspace.

        ``workspace/symbol`` support varies wildly: gopls / rust-analyzer /
        typescript-language-server / clangd / jdtls implement it well; pyright
        returns nothing unless workspace indexing is enabled; pylsp does not
        implement it at all (responds Method Not Found). When the server can't
        satisfy a workspace search, we fall back to the symbols of ``file_path``
        filtered by the query so the tool still returns something useful.
        """
        server = await self.get_server(file_path)
        if server is None:
            return no_server_error(file_path, self.list_available_servers)

        try:
            symbols = await server.workspace_symbols(query)
        except Exception:
            # Server doesn't support workspace/symbol (e.g. pylsp).
            symbols = None

        if symbols:
            results = []
            for sym in symbols[:50]:
                location = sym.get("location", {})
                results.append(
                    {
                        "name": sym.get("name", ""),
                        "kind": SymbolKind.name_for_kind(sym.get("kind", 0)),
                        "uri": location.get("uri", ""),
                        "path": uri_to_path(location.get("uri", "")),
                        "container": sym.get("containerName", ""),
                    }
                )
            return {
                "found": True,
                "query": query,
                "count": len(results),
                "symbols": results,
            }

        # Fallback: filter the seed file's document symbols by the query.
        if file_path and file_path != ".":
            doc = await self.get_document_symbols(file_path)
            if doc.get("found"):
                q = query.lower()
                matches = [
                    s
                    for s in doc.get("symbols", [])
                    if not query or q in s.get("name", "").lower()
                ]
                if matches:
                    return {
                        "found": True,
                        "query": query,
                        "count": len(matches),
                        "scope": "file",
                        "symbols": matches[:50],
                        "note": (
                            "Workspace-wide symbol search is unavailable for this "
                            "server; results are limited to the given file. "
                            "[SUGGESTION]: use Grep for a project-wide search."
                        ),
                    }

        return {
            "found": False,
            "error": (
                f"No symbols found matching '{query}'. [SUGGESTION]: this server "
                "may not support workspace symbol search — use Grep instead."
            ),
        }

    async def get_hover_info(
        self,
        file_path: str,
        line: int,
        character: int,
    ) -> dict:
        """Get hover information (type, docs) at a position."""
        server = await self.get_server(file_path)
        if server is None:
            return no_server_error(file_path, self.list_available_servers)

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
        """Rename a symbol across the workspace."""
        server = await self.get_server(file_path)
        if server is None:
            return no_server_error(
                file_path,
                self.list_available_servers,
                success_key="success",
            )

        try:
            if line == 0 and character == 0:
                position = await self._find_symbol_position(file_path, symbol_name)
                if position:
                    line, character = position

            result = await server.rename(
                file_path, line, character, new_name, dry_run=dry_run
            )
            if result:
                changes = result.get("changes") or {}
                total_edits = 0
                files_affected = []

                # Count edits from both `changes` (uri -> [TextEdit]) and the
                # newer `documentChanges` (list of TextDocumentEdit) shapes.
                for uri, edits in changes.items():
                    if isinstance(edits, list):
                        total_edits += len(edits)
                        files_affected.append(uri_to_path(uri))
                for doc_edit in result.get("documentChanges") or []:
                    if not isinstance(doc_edit, dict):
                        continue
                    edits = doc_edit.get("edits")
                    uri = (doc_edit.get("textDocument") or {}).get("uri")
                    if uri and isinstance(edits, list):
                        total_edits += len(edits)
                        files_affected.append(uri_to_path(uri))

                if dry_run:
                    return {
                        "success": True,
                        "symbol": symbol_name,
                        "new_name": new_name,
                        "dry_run": True,
                        "files_affected": len(files_affected),
                        "total_edits": total_edits,
                        "changes": changes or result.get("documentChanges"),
                    }

                # Non-dry-run: trust the server's `applied` flag rather than
                # claiming success unconditionally. If edits were returned but
                # not written, report that honestly so callers don't believe a
                # write happened when nothing changed on disk.
                applied = result.get("applied", False)
                return {
                    "success": bool(applied),
                    "symbol": symbol_name,
                    "new_name": new_name,
                    "dry_run": False,
                    "files_affected": len(files_affected),
                    "total_edits": total_edits,
                    "changes": "Applied" if applied else "not_applied",
                }
        except Exception:
            pass

        return {
            "success": False,
            "error": (
                f"Could not rename symbol '{symbol_name}'. "
                f"[SUGGESTION]: Try using Grep to find all occurrences and "
                f"Edit to change them."
            ),
        }

    async def _find_symbol_position(
        self, file_path: str, symbol_name: str
    ) -> tuple[int, int] | None:
        """Locate a symbol as ``(line, character)`` positioned ON the identifier.

        ``textDocument/definition`` / ``references`` require the cursor to sit on
        the identifier itself. Document-symbol ranges are unreliable for this:
        SymbolInformation (pylsp) reports the symbol's whole range starting at
        column 0 (the ``class``/``def`` keyword or an import line), not the name.
        So we use document symbols only to pick the best *line*, then resolve the
        exact *column* by finding the identifier within the file text.
        """
        ident = re.compile(rf"\b{re.escape(symbol_name)}\b")

        # 1. Prefer the line where the symbol is defined (from document symbols).
        candidate_line: int | None = None
        try:
            symbols = await self.get_document_symbols(file_path)
            if symbols.get("found"):
                for sym in symbols.get("symbols", []):
                    if sym.get("name") == symbol_name:
                        candidate_line = sym.get("line", 1) - 1
                        break
        except Exception:
            pass

        # 2. Resolve the exact column on the identifier. Try the candidate line
        #    first, then fall back to the first occurrence anywhere in the file.
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.read().splitlines()
            if candidate_line is not None and 0 <= candidate_line < len(lines):
                match = ident.search(lines[candidate_line])
                if match:
                    return (candidate_line, match.start())
            for i, line in enumerate(lines):
                match = ident.search(line)
                if match:
                    return (i, match.start())
        except Exception:
            pass

        return None
