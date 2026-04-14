"""Tests for llm/lsp/protocol.py - LSP protocol data structures."""

import json

import pytest

from zrb.llm.lsp.protocol import (
    Diagnostic,
    DocumentSymbol,
    Hover,
    JSONRPCMessage,
    LSPConnectionError,
    LSPError,
    LSPProtocol,
    LSPServerError,
    LSPTimeoutError,
    Location,
    Position,
    Range,
    SymbolInformation,
    SymbolKind,
)


class TestLSPErrors:
    """Test LSP exception classes."""

    def test_lsp_error_is_exception(self):
        """LSPError is a subclass of Exception."""
        assert issubclass(LSPError, Exception)

    def test_lsp_connection_error(self):
        """LSPConnectionError is a subclass of LSPError."""
        assert issubclass(LSPConnectionError, LSPError)

    def test_lsp_timeout_error(self):
        """LSPTimeoutError is a subclass of LSPError."""
        assert issubclass(LSPTimeoutError, LSPError)

    def test_lsp_server_error_init(self):
        """LSPServerError stores code, message, and data (lines 37-40)."""
        err = LSPServerError(404, "Not Found", data={"extra": "info"})
        assert err.code == 404
        assert err.message == "Not Found"
        assert err.data == {"extra": "info"}
        assert "404" in str(err)
        assert "Not Found" in str(err)

    def test_lsp_server_error_without_data(self):
        """LSPServerError works without data."""
        err = LSPServerError(500, "Internal Error")
        assert err.data is None


class TestPosition:
    """Test Position dataclass."""

    def test_to_dict(self):
        """Position.to_dict returns correct dict (line 51)."""
        pos = Position(line=3, character=15)
        result = pos.to_dict()
        assert result == {"line": 3, "character": 15}


class TestRange:
    """Test Range dataclass."""

    def test_to_dict(self):
        """Range.to_dict returns nested dict (line 62)."""
        r = Range(start=Position(0, 0), end=Position(5, 10))
        result = r.to_dict()
        assert result == {
            "start": {"line": 0, "character": 0},
            "end": {"line": 5, "character": 10},
        }


class TestLocation:
    """Test Location dataclass."""

    def test_from_dict(self):
        """Location.from_dict creates correct Location (line 74)."""
        data = {
            "uri": "file:///path/to/file.py",
            "range": {
                "start": {"line": 0, "character": 0},
                "end": {"line": 1, "character": 5},
            },
        }
        loc = Location.from_dict(data)
        assert loc.uri == "file:///path/to/file.py"
        assert loc.range.start.line == 0
        assert loc.range.end.line == 1


class TestDiagnostic:
    """Test Diagnostic dataclass."""

    def test_from_dict(self):
        """Diagnostic.from_dict creates correct Diagnostic (line 105)."""
        data = {
            "range": {
                "start": {"line": 1, "character": 0},
                "end": {"line": 1, "character": 10},
            },
            "message": "Undefined variable",
            "severity": 1,
            "source": "pylint",
            "code": "E0602",
        }
        diag = Diagnostic.from_dict(data)
        assert diag.message == "Undefined variable"
        assert diag.severity == 1
        assert diag.source == "pylint"
        assert diag.code == "E0602"

    def test_from_dict_minimal(self):
        """Diagnostic.from_dict works with minimal data."""
        data = {
            "range": {
                "start": {"line": 0, "character": 0},
                "end": {"line": 0, "character": 5},
            },
            "message": "Error",
        }
        diag = Diagnostic.from_dict(data)
        assert diag.severity == 1  # default
        assert diag.source is None
        assert diag.code is None


class TestSymbolKind:
    """Test SymbolKind enum."""

    def test_name_for_kind_known(self):
        """name_for_kind returns correct name for known kind."""
        assert SymbolKind.name_for_kind(5) == "class"
        assert SymbolKind.name_for_kind(12) == "function"

    def test_name_for_kind_unknown(self):
        """name_for_kind returns 'unknown' for unknown kind (line 154)."""
        result = SymbolKind.name_for_kind(9999)
        assert result == "unknown"


class TestDocumentSymbol:
    """Test DocumentSymbol dataclass."""

    def test_from_dict_with_children(self):
        """DocumentSymbol.from_dict handles nested children (lines 170-173)."""
        data = {
            "name": "MyClass",
            "kind": 5,
            "range": {
                "start": {"line": 0, "character": 0},
                "end": {"line": 10, "character": 0},
            },
            "selectionRange": {
                "start": {"line": 0, "character": 6},
                "end": {"line": 0, "character": 13},
            },
            "detail": "class definition",
            "children": [
                {
                    "name": "my_method",
                    "kind": 6,
                    "range": {
                        "start": {"line": 1, "character": 4},
                        "end": {"line": 5, "character": 4},
                    },
                    "selectionRange": {
                        "start": {"line": 1, "character": 8},
                        "end": {"line": 1, "character": 17},
                    },
                    "children": [],
                }
            ],
        }
        symbol = DocumentSymbol.from_dict(data)
        assert symbol.name == "MyClass"
        assert symbol.detail == "class definition"
        assert len(symbol.children) == 1
        assert symbol.children[0].name == "my_method"


class TestSymbolInformation:
    """Test SymbolInformation dataclass."""

    def test_from_dict(self):
        """SymbolInformation.from_dict creates correct object (line 200)."""
        data = {
            "name": "my_func",
            "kind": 12,
            "location": {
                "uri": "file:///test.py",
                "range": {
                    "start": {"line": 5, "character": 0},
                    "end": {"line": 10, "character": 0},
                },
            },
            "containerName": "MyModule",
        }
        sym = SymbolInformation.from_dict(data)
        assert sym.name == "my_func"
        assert sym.kind == 12
        assert sym.container_name == "MyModule"

    def test_from_dict_without_container(self):
        """SymbolInformation.from_dict works without containerName."""
        data = {
            "name": "my_func",
            "kind": 12,
            "location": {
                "uri": "file:///test.py",
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 5, "character": 0},
                },
            },
        }
        sym = SymbolInformation.from_dict(data)
        assert sym.container_name is None


class TestHover:
    """Test Hover dataclass."""

    def test_from_dict_with_range(self):
        """Hover.from_dict creates correct Hover with range (line 217)."""
        data = {
            "contents": "Function documentation",
            "range": {
                "start": {"line": 0, "character": 0},
                "end": {"line": 0, "character": 10},
            },
        }
        hover = Hover.from_dict(data)
        assert hover.contents == "Function documentation"
        assert hover.range is not None
        assert hover.range.start.line == 0

    def test_from_dict_without_range(self):
        """Hover.from_dict creates correct Hover without range."""
        data = {"contents": "Simple content"}
        hover = Hover.from_dict(data)
        assert hover.contents == "Simple content"
        assert hover.range is None


class TestJSONRPCMessage:
    """Test JSONRPCMessage static methods."""

    def test_create_request_with_params(self):
        """create_request with params creates valid JSON-RPC message (lines 240-245)."""
        msg = JSONRPCMessage.create_request(
            "textDocument/definition",
            params={"textDocument": {"uri": "file:///test.py"}, "position": {"line": 5, "character": 10}},
            request_id=42,
        )
        parsed = json.loads(msg)
        assert parsed["jsonrpc"] == "2.0"
        assert parsed["id"] == 42
        assert parsed["method"] == "textDocument/definition"
        assert "params" in parsed

    def test_create_request_without_id(self):
        """create_request generates UUID when id is None."""
        msg = JSONRPCMessage.create_request("test/method")
        parsed = json.loads(msg)
        assert "id" in parsed
        assert parsed["id"] is not None

    def test_create_notification_with_params(self):
        """create_notification with params (lines 250-253)."""
        msg = JSONRPCMessage.create_notification(
            "textDocument/didOpen",
            params={"textDocument": {"uri": "file:///test.py"}},
        )
        parsed = json.loads(msg)
        assert parsed["jsonrpc"] == "2.0"
        assert parsed["method"] == "textDocument/didOpen"
        assert "id" not in parsed
        assert "params" in parsed

    def test_create_notification_without_params(self):
        """create_notification without params."""
        msg = JSONRPCMessage.create_notification("exit")
        parsed = json.loads(msg)
        assert "params" not in parsed

    def test_parse_response(self):
        """parse_response extracts id, result, error (lines 264-268)."""
        response = json.dumps({
            "jsonrpc": "2.0",
            "id": "test-id",
            "result": [{"uri": "file:///test.py"}],
        })
        request_id, result, error = JSONRPCMessage.parse_response(response)
        assert request_id == "test-id"
        assert len(result) == 1
        assert error is None

    def test_create_content_length_header(self):
        """create_content_length_header formats correctly (line 279)."""
        content = '{"jsonrpc":"2.0"}'
        header = JSONRPCMessage.create_content_length_header(content)
        assert header.startswith(f"Content-Length: {len(content)}\r\n\r\n")
        assert header.endswith(content)


class TestLSPProtocol:
    """Test LSPProtocol class methods."""

    def test_create_initialize_params(self):
        """create_initialize_params creates valid init params (lines 313-323)."""
        params = LSPProtocol.create_initialize_params("/path/to/project")
        assert "rootUri" in params
        assert params["rootUri"].startswith("file://")
        assert params["processId"] is None
        assert "capabilities" in params

    def test_create_initialize_params_with_options(self):
        """create_initialize_params passes initializationOptions."""
        options = {"pylsp": {"plugins": {"pycodestyle": {"enabled": False}}}}
        params = LSPProtocol.create_initialize_params("/path", initialization_options=options)
        assert params["initializationOptions"] == options

    def test_create_text_document_identifier(self):
        """create_text_document_identifier creates file URI (lines 334-338)."""
        identifier = LSPProtocol.create_text_document_identifier("/path/to/file.py")
        assert "uri" in identifier
        assert identifier["uri"].startswith("file://")
        assert "file.py" in identifier["uri"]

    def test_create_position(self):
        """create_position creates correct position dict (line 343)."""
        pos = LSPProtocol.create_position(5, 10)
        assert pos == {"line": 5, "character": 10}
