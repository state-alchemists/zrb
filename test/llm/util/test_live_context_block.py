from zrb.llm.util.live_context_block import split_live_context


def test_split_live_context_returns_none_when_absent():
    message, block = split_live_context("just a plain message")
    assert message == "just a plain message"
    assert block is None


def test_split_live_context_splits_trailing_block():
    content = (
        "what's the weather\n\n<live-context>\n- Time: 2026-01-01\n</live-context>"
    )
    message, block = split_live_context(content)
    assert message == "what's the weather"
    assert block == "<live-context>\n- Time: 2026-01-01\n</live-context>"


def test_split_live_context_handles_block_only_content():
    content = "<live-context>\n- Time: 2026-01-01\n</live-context>"
    message, block = split_live_context(content)
    assert message == ""
    assert block == content


def test_split_live_context_handles_empty_string():
    message, block = split_live_context("")
    assert message == ""
    assert block is None


def test_split_live_context_handles_nested_journal_index():
    content = (
        "hello\n\n<live-context>\n- Time: now\n"
        "<journal-index>\nsome facts\n</journal-index>\n"
        "</live-context>"
    )
    message, block = split_live_context(content)
    assert message == "hello"
    assert block is not None
    assert "<journal-index>" in block
    assert block.endswith("</live-context>")
