"""Tests for llm/lsp/manager/symbol_utils.py."""

from zrb.llm.lsp.manager.symbol_utils import format_document_symbols, uri_to_path


def test_uri_to_path_strips_scheme():
    assert uri_to_path("file:///home/user/foo.py") == "/home/user/foo.py"


def test_uri_to_path_decodes_percent_escapes():
    assert uri_to_path("file:///tmp/my%20file.py") == "/tmp/my file.py"


def test_uri_to_path_passes_through_non_file_uri():
    assert uri_to_path("http://example.com/x") == "http://example.com/x"
    assert uri_to_path("/already/a/path") == "/already/a/path"


def test_format_document_symbols_flattens_top_level():
    syms = [
        {
            "name": "foo",
            "kind": 12,  # Function
            "range": {"end": {"line": 9}},
            "selectionRange": {"start": {"line": 0, "character": 4}},
            "detail": "(x: int) -> int",
        },
    ]
    out = format_document_symbols(syms)
    assert len(out) == 1
    assert out[0]["name"] == "foo"
    assert out[0]["line"] == 1  # 0-based → 1-based
    assert out[0]["end_line"] == 10
    assert out[0]["character"] == 4
    assert out[0]["depth"] == 0
    assert out[0]["detail"] == "(x: int) -> int"


def test_format_document_symbols_recurses_into_children():
    syms = [
        {
            "name": "MyClass",
            "kind": 5,  # Class
            "range": {"end": {"line": 20}},
            "selectionRange": {"start": {"line": 0, "character": 6}},
            "children": [
                {
                    "name": "method",
                    "kind": 6,  # Method
                    "range": {"end": {"line": 10}},
                    "selectionRange": {"start": {"line": 2, "character": 4}},
                }
            ],
        }
    ]
    out = format_document_symbols(syms)
    assert [s["name"] for s in out] == ["MyClass", "method"]
    assert out[0]["depth"] == 0
    assert out[1]["depth"] == 1


def test_format_document_symbols_skips_non_dict_entries():
    syms = ["not a dict", None, {"name": "ok", "kind": 0}]
    out = format_document_symbols(syms)
    assert [s["name"] for s in out] == ["ok"]
