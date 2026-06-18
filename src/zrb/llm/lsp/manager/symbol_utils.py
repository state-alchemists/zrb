"""Stateless helpers used by `LSPManager` to format symbols and parse URIs."""

from __future__ import annotations

from urllib.parse import unquote, urlparse

from zrb.llm.lsp.protocol import SymbolKind


def uri_to_path(uri: str) -> str:
    """Convert a `file://` URI to a filesystem path. Pass-through otherwise."""
    if uri.startswith("file://"):
        return unquote(urlparse(uri).path)
    return uri


def format_document_symbols(symbols: list, depth: int = 0) -> list[dict]:
    """Flatten LSP document symbols into a list with hierarchy depth.

    Handles both response shapes ``textDocument/documentSymbol`` may return:

    * **DocumentSymbol** (hierarchical; pyright, gopls, …) — position in
      ``range``/``selectionRange``, with nested ``children``.
    * **SymbolInformation** (flat; pylsp, …) — position in ``location.range``,
      no children.

    Reading positions from the wrong field yielded ``line=1, character=0`` for
    every SymbolInformation symbol, which corrupted symbol-position lookups
    (``find_definition`` / ``find_references`` resolved nothing on pylsp).
    """
    results: list[dict] = []
    for sym in symbols:
        if not isinstance(sym, dict):
            continue
        if "location" in sym:
            # SymbolInformation: position lives under location.range.
            range_info = sym.get("location", {}).get("range", {})
            selection_range = range_info
        else:
            # DocumentSymbol: full range + a selectionRange on the name.
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
