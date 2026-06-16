"""Tests for llm/lsp/protocol.py - LSP protocol data structures."""

import json

import pytest

from zrb.llm.lsp.protocol import (
    JSONRPCMessage,
    LSPError,
    LSPProtocol,
    LSPServerError,
    LSPTimeoutError,
    SymbolKind,
)


class TestLSPErrors:
    """Test LSP exception classes."""

    def test_lsp_error_is_exception(self):
        """LSPError is a subclass of Exception."""
        assert issubclass(LSPError, Exception)

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


class TestJSONRPCMessage:
    """Test JSONRPCMessage static methods."""

    def test_create_request_with_params(self):
        """create_request with params creates valid JSON-RPC message (lines 240-245)."""
        msg = JSONRPCMessage.create_request(
            "textDocument/definition",
            params={
                "textDocument": {"uri": "file:///test.py"},
                "position": {"line": 5, "character": 10},
            },
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

    def test_create_content_length_header(self):
        """create_content_length_header formats correctly (line 279)."""
        content = '{"jsonrpc":"2.0"}'
        header = JSONRPCMessage.create_content_length_header(content)
        assert header.startswith(f"Content-Length: {len(content)}\r\n\r\n")
        assert header.endswith(content)


class TestLSPProtocol:
    """Test LSPProtocol class methods."""

    def test_create_text_document_identifier(self):
        """create_text_document_identifier creates file URI (lines 334-338)."""
        identifier = LSPProtocol.create_text_document_identifier("/path/to/file.py")
        assert "uri" in identifier
        assert identifier["uri"].startswith("file://")
        assert "file.py" in identifier["uri"]
