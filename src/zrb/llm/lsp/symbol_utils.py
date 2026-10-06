"""Stateless helpers used by `LSPManager` to format symbols and parse URIs."""

from __future__ import annotations

import re
from urllib.parse import unquote, urlparse

from zrb.llm.lsp.protocol import SymbolKind


def uri_to_path(uri: str) -> str:
    """Convert a `file://` URI to a filesystem path. Pass-through otherwise."""
    if not uri.startswith("file://"):
        return uri
    path = unquote(urlparse(uri).path)
    # Windows: "file:///D:/x.py" parses to "/D:/x.py"; drop the leading slash.
    if re.match(r"^/[A-Za-z]:", path):
        return path[1:]
    return path


def format_document_symbols(symbols: list, depth: int = 0) -> list[dict]:
    """Flatten LSP document symbols into a list with hierarchy depth.

    Accepts both hierarchical DocumentSymbol and flat SymbolInformation shapes.
    """
    results: list[dict] = []
    for sym in symbols:
        if not isinstance(sym, dict):
            continue
        if "location" in sym:
            range_info = sym.get("location", {}).get("range", {})
            selection_range = range_info
        else:
            range_info = sym.get("range", {})
            selection_range = sym.get("selectionRange", range_info)
        results.append(
            {
                "name": sym.get("name", ""),
                "kind": SymbolKind.name_for_kind(sym.get("kind", 0)),
                "line": selection_range.get("start", {}).get("line", 0) + 1,
                "end_line": range_info.get("end", {}).get("line", 0) + 1,
                "character": selection_range.get("start", {}).get("character", 0),
                "detail": sym.get("detail", ""),
                "depth": depth,
            }
        )
        children = sym.get("children", [])
        if children:
            results.extend(format_document_symbols(children, depth + 1))
    return results
