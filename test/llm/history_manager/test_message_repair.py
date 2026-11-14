"""The rules a stored payload is repaired by, on plain dicts.

These are the shapes a history file holds when an older zrb, a different
provider, or a hand edit wrote it. They are tested here, on a payload in and a
payload out, rather than through a file: nothing in this module touches disk,
and a test that went through one would be testing the store again.
"""

from zrb.llm.history_manager.message_repair import (
    clean_corrupted_content,
    filter_empty_responses,
    sanitize_history,
)


def test_content_is_cleaned_before_empties_are_dropped():
    """The pass order is the rule, and this is the case where it shows.

    A custom part's null content disappears while cleaning, which leaves the
    part with a kind and nothing to validate. Judged before cleaning, the same
    part would have had null content and been thrown away.
    """
    data = [{"kind": "request", "parts": [{"part_kind": "custom", "content": None}]}]

    assert sanitize_history(data) == [
        {"kind": "request", "parts": [{"part_kind": "custom"}]}
    ]


def test_a_request_whose_parts_all_vanish_is_dropped():
    data = [{"kind": "request", "parts": [{"part_kind": "tool-call"}], "id": "m1"}]

    assert sanitize_history(data) == []


def test_a_text_part_with_no_content_drops_the_message_that_held_it():
    data = [{"kind": "response", "parts": [{"part_kind": "text", "content": None}]}]

    assert sanitize_history(data) == []


def test_a_message_that_still_has_a_part_is_kept():
    data = [{"kind": "request", "parts": [{"part_kind": "user-prompt", "content": "hi"}]}]

    assert filter_empty_responses(data) == data


def test_an_unknown_part_kind_keeps_its_fields_and_its_children():
    data = {
        "parts": [
            {
                "part_kind": "audio-part",
                "content": None,
                "extra": {"gone": None, "kept": 1},
            }
        ]
    }

    assert clean_corrupted_content(data) == {
        "parts": [{"part_kind": "audio-part", "extra": {"kept": 1}}]
    }


def test_a_tool_return_part_names_an_unknown_tool_and_drops_empty_correlation():
    data = {
        "part_kind": "tool-return",
        "content": "ok",
        "tool_name": "",
        "tool_call_id": "",
        "timestamp": "",
        "outcome": "retried",
    }

    assert clean_corrupted_content(data) == {
        "part_kind": "tool-return",
        "content": "ok",
        "tool_name": "unknown",
        "outcome": "retried",
    }


def test_a_tool_call_part_without_a_tool_name_is_not_a_part():
    assert clean_corrupted_content({"part_kind": "tool-call", "args": {}}) is None


def test_a_text_like_part_keeps_its_structural_fields():
    data = {"part_kind": "thinking", "content": "why", "signature": "sig", "id": "th-1"}

    assert clean_corrupted_content(data) == data


def test_an_attachment_is_kept_whole_rather_than_flattened_to_text():
    attachment = {"kind": "binary", "data": "AAAA", "media_type": "image/png"}

    cleaned = clean_corrupted_content({"part_kind": "user-prompt", "content": [attachment]})

    assert cleaned["content"] == [attachment]


def test_a_user_prompt_holding_something_else_is_flattened_to_text():
    cleaned = clean_corrupted_content(
        {"part_kind": "user-prompt", "content": [{"kind": "tool-return", "x": 1}]}
    )

    assert isinstance(cleaned["content"], str)


def test_a_scalar_is_returned_as_it_came():
    assert sanitize_history(42) == 42
