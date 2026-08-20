from types import SimpleNamespace

from zrb.llm.ui.base.replay import BaseUIReplay


class MockUI:
    """Stand-in for `BaseUI`: owns the state/methods `BaseUIReplay` reads
    through the owner reference, and composes a real `BaseUIReplay(self)`."""

    def __init__(self):
        self.calls = []  # list of (text, kind)
        self._replay_impl = BaseUIReplay(self)

    def append_to_output(self, *values, kind="text", **kwargs):
        self.calls.append((" ".join(str(v) for v in values), kind))

    def append_markdown(self, markdown_text):
        self.calls.append((markdown_text, "markdown"))

    def _get_output_field_width(self):
        return 80

    def replay_history(self, messages):
        return self._replay_impl.replay_history(messages)


def _user_message(content):
    return SimpleNamespace(
        kind="request",
        timestamp=None,
        parts=[SimpleNamespace(part_kind="user-prompt", content=content)],
    )


def test_replay_plain_user_message_has_no_live_context_output():
    ui = MockUI()
    ui.replay_history([_user_message("hello there")])

    texts = [text for text, _kind in ui.calls]
    kinds = [kind for _text, kind in ui.calls]
    assert any("hello there" in t for t in texts)
    assert "live_context" not in kinds


def test_replay_strips_live_context_and_renders_it_faint():
    ui = MockUI()
    content = "hello there\n\n<live-context>\n- Time: now\n</live-context>"
    ui.replay_history([_user_message(content)])

    user_line = next(text for text, kind in ui.calls if kind == "text")
    live_context_line = next(text for text, kind in ui.calls if kind == "live_context")
    assert "hello there" in user_line
    assert "<live-context>" not in user_line
    assert "- Time: now" in live_context_line


def test_replay_user_message_that_is_only_live_context():
    ui = MockUI()
    content = "<live-context>\n- Time: now\n</live-context>"
    ui.replay_history([_user_message(content)])

    user_line = next(text for text, kind in ui.calls if kind == "text")
    live_context_line = next(text for text, kind in ui.calls if kind == "live_context")
    assert user_line.strip().endswith(">>")
    assert "- Time: now" in live_context_line


def test_replay_non_string_content_is_not_split():
    ui = MockUI()
    ui.replay_history([_user_message(["hi", object()])])

    kinds = [kind for _text, kind in ui.calls]
    assert "live_context" not in kinds
