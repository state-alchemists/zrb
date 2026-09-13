"""Tests for the shared live/replay user-message echo."""

from zrb.llm.ui.base.user_echo import echo_user_message, should_render_user_markdown


def test_should_render_user_markdown_detects_markdownish_text():
    assert should_render_user_markdown("plain single line") is False
    # Prices are not math blocks — a lone `$` must not trigger rendering.
    assert should_render_user_markdown("What is $5?") is False
    assert should_render_user_markdown("**bold**") is True
    assert should_render_user_markdown("`inline code`") is True
    assert should_render_user_markdown("[zrb](https://zrb.io)") is True
    assert should_render_user_markdown("## Plan\n\n- a\n- b") is True
    assert should_render_user_markdown("```python\nx = 1\n```") is True
    assert should_render_user_markdown("```mermaid\ngraph TD; A-->B\n```") is True
    assert should_render_user_markdown("| a | b |\n| - | - |\n| 1 | 2 |") is True
    assert should_render_user_markdown("> quoted") is True
    assert (
        should_render_user_markdown("\\begin{matrix}\na & b \\\\\nc & d\n\\end{matrix}")
        is True
    )


def test_should_render_user_markdown_leaves_plain_multiline_pastes_alone():
    """Line count is not a markdown signal. Rendering a traceback, a log dump
    or unfenced code collapses every line break into one paragraph."""
    assert should_render_user_markdown("can you fix this\nit is broken") is False
    assert (
        should_render_user_markdown(
            'Traceback (most recent call last):\n'
            '  File "app.py", line 12, in <module>\n'
            "    x = cfg[__main__]\n"
            "KeyError: '__main__'"
        )
        is False
    )
    assert (
        should_render_user_markdown(
            "2026-09-13 10:00:02 ERROR conn *failed* to host_a_b_c\n"
            "2026-09-13 10:00:03 WARN  retry 1/3"
        )
        is False
    )
    assert (
        should_render_user_markdown(
            "def f(x):\n    if x_val_y and z:\n        return [1, 2, 3]"
        )
        is False
    )


def test_echo_user_message_returns_the_verbatim_echo_for_plain_text():
    outputs = []
    echo = echo_user_message(
        lambda *v, **k: outputs.append("".join(str(x) for x in v) + k.get("end", "")),
        lambda text: (_ for _ in ()).throw(AssertionError("must not render")),
        header="\n>> ",
        body="plain text",
    )
    assert echo == "\n>> plain text\n"
    assert outputs == [echo]


def test_echo_user_message_renders_markdown_and_claims_no_span():
    outputs = []
    rendered = []
    echo = echo_user_message(
        lambda *v, **k: outputs.append((v, k)),
        rendered.append,
        header="\n>> ",
        body="**bold**",
    )
    assert echo == ""
    assert rendered == ["**bold**"]
    assert outputs == [(("\n>> ",), {"end": ""})]


def test_echo_user_message_falls_back_when_no_renderer_is_available():
    """A UI without append_markdown still gets a verbatim echo."""
    outputs = []
    echo = echo_user_message(
        lambda *v, **k: outputs.append(v),
        None,
        header="\n>> ",
        body="**bold**",
    )
    assert echo == "\n>> **bold**\n"
