from unittest.mock import MagicMock, patch

from zrb.llm.ui.default.app.completion.args import (
    complete_copy_arg,
    complete_exec_arg,
    complete_load_arg,
    complete_redirect_arg,
    complete_save_arg,
    complete_set_value_arg,
)


def test_complete_save_arg_yields_existing_sessions():
    hm = MagicMock()
    hm.search.return_value = ["alpha", "beta"]
    results = list(complete_save_arg("a", hm))
    completions = [c.text for c in results]
    assert "alpha" in completions
    assert "beta" in completions


def test_complete_load_arg_caps_at_fifty_results():
    hm = MagicMock()
    hm.search.return_value = [f"sess-{i}" for i in range(80)]
    results = list(complete_load_arg("sess", hm))
    assert len(results) == 50


def test_complete_load_arg_excludes_delegated_sessions_from_search():
    hm = MagicMock()
    hm.search.return_value = ["foo-sub-bar-deadbeef"]
    results = [c.text for c in complete_load_arg("foo", hm)]
    hm.search.assert_called_once_with("foo", include_delegated=False)
    assert results == ["foo-sub-bar-deadbeef"]


def test_complete_redirect_arg_silent_when_prefix_doesnt_match_timestamp():
    """If prefix is 'zzz', the timestamp-based suggestion is suppressed."""
    results = list(complete_redirect_arg("zzz"))
    assert results == []


def test_complete_redirect_arg_yields_response_prefixed_timestamp():
    """Empty prefix yields a single response-<timestamp>.txt suggestion."""
    results = list(complete_redirect_arg(""))
    assert len(results) == 1
    assert results[0].text.startswith("response-")
    assert results[0].text.endswith(".txt")


def test_complete_copy_arg_silent_when_prefix_doesnt_match():
    """If prefix is 'zzz', the copy suggestion is suppressed."""
    results = list(complete_copy_arg("zzz"))
    assert results == []


def test_complete_copy_arg_yields_transcript_prefixed_timestamp():
    """Empty prefix yields a single transcript-<timestamp>.txt suggestion."""
    results = list(complete_copy_arg(""))
    assert len(results) == 1
    assert results[0].text.startswith("transcript-")
    assert results[0].text.endswith(".txt")


def test_complete_exec_arg_returns_recent_first():
    cmd_history = ["echo hi", "echo bye", "ls -la"]
    results = list(complete_exec_arg("echo", cmd_history))
    texts = [c.text for c in results]
    # Most recent first → "echo bye" before "echo hi"
    assert texts == ["echo bye", "echo hi"]


def test_complete_exec_arg_filters_by_prefix():
    cmd_history = ["echo hi", "ls -la", "grep foo"]
    results = list(complete_exec_arg("ls", cmd_history))
    assert [c.text for c in results] == ["ls -la"]


def test_complete_set_value_arg_normalizes_lowercase_name(monkeypatch):
    """`/set llm_model <tab>` offers model names and the current value,
    matching the handler's case-insensitive name acceptance."""
    monkeypatch.setenv("ZRB_LLM_MODEL", "openai:current-model")
    results = list(
        complete_set_value_arg("llm_model", "", ["openai:gpt-4o", "openai:gpt-4o-mini"])
    )
    assert any(c.text == "openai:gpt-4o" for c in results)
    assert any(c.display_meta_text == "Model Name" for c in results)
    current = [c.text for c in results if c.display_meta_text == "Current value"]
    assert current == ["openai:current-model"]


def test_complete_set_value_arg_serializes_a_list_value(monkeypatch):
    """A list-valued setting is offered as the comma-separated text its cast
    reads back, so selecting it round-trips to the same list -- not Python-list
    syntax (``['/set']``) that the field would parse as one bracketed entry
    (round-3 review)."""
    from zrb.config.config import CFG

    monkeypatch.setenv("ZRB_LLM_UI_COMMAND_SET", "/set, /configure")
    results = list(complete_set_value_arg("LLM_UI_COMMAND_SET", "", []))
    current = [c.text for c in results if c.display_meta_text == "Current value"]
    assert current == ["/set,/configure"]
    field = CFG.get_settable_field("LLM_UI_COMMAND_SET")
    assert field.cast(current[0]) == CFG.LLM_UI_COMMAND_SET == ["/set", "/configure"]
