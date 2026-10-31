from zrb.util.truncate import (
    truncate_chars,
    truncate_display,
    truncate_items,
    truncate_text,
)


# --- truncate_text ---
def test_truncate_text_no_truncation():
    text = "a\nb\nc"
    out, truncated = truncate_text(text, 100)
    assert out == text
    assert truncated is False


def test_truncate_text_keep_head():
    text = "\n".join(f"line{i}" for i in range(100))
    out, truncated = truncate_text(text, 30, keep="head")
    assert truncated is True
    assert out.startswith("line0")
    assert out.endswith("...[TRUNCATED]")
    assert "line99" not in out


def test_truncate_text_keep_tail():
    text = "\n".join(f"line{i}" for i in range(100))
    out, truncated = truncate_text(text, 30, keep="tail")
    assert truncated is True
    assert out.startswith("[TRUNCATED]...")
    assert "line99" in out
    assert "line0\n" not in out


def test_truncate_text_keep_tail_zero_max_chars():
    out, truncated = truncate_text("a\nb\nc", 0, keep="tail")
    assert truncated is True
    assert out == "[TRUNCATED]...\n"


def test_truncate_text_keep_tail_negative_max_chars():
    out, truncated = truncate_text("a\nb\nc", -2, keep="tail")
    assert truncated is True
    assert out == "[TRUNCATED]...\n"


def test_truncate_text_snaps_to_line_boundary_head():
    text = "aaaa\nbbbb\ncccc\n"
    out, _ = truncate_text(text, 6, keep="head")
    assert out == "aaaa\n...[TRUNCATED]"


def test_truncate_text_keep_head_single_long_line():
    text = "x" * 50
    out, truncated = truncate_text(text, 10, keep="head")
    assert truncated is True
    assert out == "x" * 10 + "\n...[TRUNCATED]"


# --- truncate_items ---
def test_truncate_items_no_truncation():
    items = ["a", "b", "c"]
    kept, omitted = truncate_items(items, 1000)
    assert kept == items
    assert omitted == 0


def test_truncate_items_truncates():
    items = [f"file{i}.py" for i in range(100)]
    kept, omitted = truncate_items(items, 30)
    assert omitted > 0
    assert len(kept) + omitted == 100
    assert kept[0] == "file0.py"


def test_truncate_items_keeps_first_even_if_huge():
    items = ["x" * 1000, "y", "z"]
    kept, omitted = truncate_items(items, 10)
    assert kept == ["x" * 1000]
    assert omitted == 2


# --- truncate_display ---
def test_truncate_display_no_truncation():
    assert truncate_display("short", 100) == "short"


def test_truncate_display_normal_truncation():
    out = truncate_display("a" * 80, 30)
    assert len(out) == 30
    assert out.endswith("...")


def test_truncate_display_never_exceeds_max_chars_for_small_budgets():
    text = "a" * 80
    for max_chars in (0, 1, 2, 3):
        out = truncate_display(text, max_chars)
        assert len(out) <= max_chars


def test_truncate_display_small_budget_has_no_ellipsis():
    assert truncate_display("abcdef", 2) == "ab"
    assert truncate_display("abcdef", 0) == ""


# --- truncate_chars (unchanged) ---
def test_truncate_chars_no_truncation():
    assert truncate_chars("short", 100) == "short"


def test_truncate_chars_truncates():
    out = truncate_chars("abcdef", 3)
    assert out.startswith("abc")
    assert "TRUNCATED" in out


def test_the_live_stream_and_the_exported_transcript_agree():
    """One tool call must render the same in both views.

    `history_formatter` and `stream_response` each used to carry a private
    `_truncate_kwargs` — same name, same package, same 30-char default, and
    different output: one elided as `val[:27] + "..."`, the other as
    `arg[:26] + " ..."`, so the exported transcript and the live stream
    disagreed by a character on the same call. Both now share
    `zrb.llm.util.tool_args.truncate_tool_args_values`.

    Asserted through the public surface: the transcript renderer's output must
    equal `truncate_display`, and both renderers must be bound to
    `tool_args`'s shared helper rather than to a copy of its logic.
    """
    import json

    from zrb.llm.util import history_formatter, stream_response
    from zrb.llm.util.history_formatter import format_args
    from zrb.llm.util.tool_args import truncate_tool_args_values
    from zrb.util.truncate import truncate_display

    value = "x" * 80
    exported = json.loads(format_args({"path": value}))["path"]

    assert exported == truncate_display(value, 30)
    assert len(exported) == 30 and exported.endswith("...")
    assert stream_response.truncate_tool_args_values is truncate_tool_args_values
    assert history_formatter.truncate_tool_args_values is truncate_tool_args_values
