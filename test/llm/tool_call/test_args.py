from unittest.mock import MagicMock

from zrb.llm.tool_call.args import (
    is_empty_tool_args,
    parse_tool_args,
    truncate_tool_args_values,
)


def _call_with_args(args):
    call = MagicMock()
    call.args = args
    return call


def test_parse_tool_args_passes_through_dict():
    assert parse_tool_args(_call_with_args({"path": "a.txt"})) == {"path": "a.txt"}


def test_parse_tool_args_parses_json_string():
    assert parse_tool_args(_call_with_args('{"path": "a.txt"}')) == {"path": "a.txt"}


def test_parse_tool_args_returns_none_on_invalid_json():
    assert parse_tool_args(_call_with_args("not json")) is None


def test_parse_tool_args_returns_none_when_parsed_value_is_not_a_dict():
    assert parse_tool_args(_call_with_args("[1, 2, 3]")) is None


def test_parse_tool_args_returns_none_for_non_dict_non_string_args():
    assert parse_tool_args(_call_with_args([1, 2, 3])) is None


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
