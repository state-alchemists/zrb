"""Tests for the shared tool-call args helpers used by stream_response.py and
history_formatter.py."""

from zrb.llm.util.tool_args import (
    is_empty_tool_args,
    parse_tool_args_dict,
    truncate_tool_args_values,
)


class TestIsEmptyToolArgs:
    def test_none_is_empty(self):
        assert is_empty_tool_args(None) is True

    def test_empty_string_is_empty(self):
        assert is_empty_tool_args("") is True

    def test_null_string_is_empty(self):
        assert is_empty_tool_args("null") is True

    def test_empty_json_object_string_is_empty(self):
        assert is_empty_tool_args("{}") is True

    def test_whitespace_around_sentinel_is_empty(self):
        assert is_empty_tool_args("  null  ") is True

    def test_non_empty_dict_is_not_empty(self):
        assert is_empty_tool_args({"key": "value"}) is False

    def test_non_empty_string_is_not_empty(self):
        assert is_empty_tool_args('{"key": "value"}') is False


class TestParseToolArgsDict:
    def test_dict_passes_through(self):
        assert parse_tool_args_dict({"key": "value"}) == {"key": "value"}

    def test_json_dict_string_parses(self):
        assert parse_tool_args_dict('{"key": "value"}') == {"key": "value"}

    def test_invalid_json_string_returns_none(self):
        assert parse_tool_args_dict("not json") is None

    def test_valid_json_non_dict_string_returns_none(self):
        assert parse_tool_args_dict("[1, 2, 3]") is None

    def test_non_string_non_dict_returns_none(self):
        assert parse_tool_args_dict(12345) is None


class TestTruncateToolArgsValues:
    def test_truncates_long_string_values(self):
        result = truncate_tool_args_values({"short": "abc", "long": "a" * 50})
        assert result["short"] == "abc"
        assert len(result["long"]) == 30
        assert "..." in result["long"]

    def test_leaves_non_string_values_untouched(self):
        result = truncate_tool_args_values({"n": 12345})
        assert result["n"] == 12345

    def test_full_skips_truncation(self):
        result = truncate_tool_args_values({"long": "a" * 50}, full=True)
        assert result["long"] == "a" * 50

    def test_respects_custom_max_length(self):
        result = truncate_tool_args_values({"long": "a" * 50}, max_length=10)
        assert len(result["long"]) == 10
