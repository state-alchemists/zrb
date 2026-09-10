from unittest.mock import MagicMock

from zrb.llm.tool_call.args import parse_tool_args


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
