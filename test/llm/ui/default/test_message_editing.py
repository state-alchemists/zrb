import gc
import weakref
from unittest.mock import patch

from zrb.llm.ui.base.message_queue import EchoSpan, QueuedMessage


def make_entry(text="original", marker="💬", ts="10:00"):
    async def run():
        pass

    entry = QueuedMessage(text=text, attachments=[], kind="message", run=run)
    entry.echo_marker = marker
    entry.echo_timestamp = ts
    return entry


def test_track_echo_span_records_when_echo_lands(editing_ui):
    echo = "\n💬 10:00 >> original\n"
    editing_ui.output_field.text = "head" + echo
    entry = make_entry()

    editing_ui.track_echo_span(entry, echo)

    span = entry.echo_spans[editing_ui]
    assert (span.start, span.end) == (len("head"), len("head") + len(echo))
    assert span.text == echo


def test_track_echo_span_records_with_writers_trailing_newline(editing_ui):
    # The writer's default separator appends a newline after the echo, so a
    # bare `endswith` span would never record and pastes would fragment.
    echo = "\n💬 10:00 >> original\n"
    editing_ui.output_field.text = "head" + echo + "\n"
    entry = make_entry()

    editing_ui.track_echo_span(entry, echo)

    span = entry.echo_spans[editing_ui]
    assert (span.start, span.end) == (len("head"), len("head") + len(echo))
    assert editing_ui.output_text[span.start : span.end] == echo


def test_track_echo_span_skips_when_echo_buffered(editing_ui):
    # A pending confirmation diverted the echo from the buffer — nothing to
    # splice later, so the span must not be recorded.
    editing_ui.output_field.text = "confirmation prompt"
    entry = make_entry()

    editing_ui.track_echo_span(entry, "\n💬 10:00 >> original\n")

    assert entry.echo_spans == {}


def test_redraw_echo_splices_edited_line(editing_ui):
    echo = "\n💬 10:00 >> original\n"
    editing_ui.output_field.text = "head" + echo + "tail"
    entry = make_entry()
    start = len("head")
    entry.echo_spans[editing_ui] = EchoSpan(start, start + len(echo), echo)

    entry.text = "edited text"
    editing_ui.redraw_echo(entry)

    assert editing_ui.output_text == "head" + "\n💬 10:00 >> edited text\n" + "tail"
    span = entry.echo_spans[editing_ui]
    assert span.start == start
    assert span.end == start + len("\n💬 10:00 >> edited text\n")
    assert span.text == "\n💬 10:00 >> edited text\n"


def test_redraw_echo_drops_span_that_no_longer_holds_the_echo(editing_ui):
    # A terminal resize shifted the transcript without updating the span;
    # splicing at the stale span would corrupt the output, so it is dropped.
    echo = "\n💬 10:00 >> original\n"
    editing_ui.output_field.text = "rewrapped long block now" + echo
    entry = make_entry()
    stale_start = len("old short block")  # span recorded when the block was short
    entry.echo_spans[editing_ui] = EchoSpan(stale_start, stale_start + len(echo), echo)

    entry.text = "edited text"
    editing_ui.redraw_echo(entry)

    assert editing_ui.output_text == "rewrapped long block now" + echo  # untouched
    assert entry.echo_spans == {}


def test_redraw_echo_uses_entry_marker_and_timestamp(editing_ui):
    echo = "\n⏳ 10:00 >> original\n"
    editing_ui.output_field.text = echo
    entry = make_entry()
    entry.echo_marker = "⏳"
    entry.echo_spans[editing_ui] = EchoSpan(0, len(echo), echo)

    entry.text = "edited"
    editing_ui.redraw_echo(entry)

    assert editing_ui.output_text == "\n⏳ 10:00 >> edited\n"


def test_redraw_echo_drops_stale_span(editing_ui):
    entry = make_entry()
    entry.echo_spans[editing_ui] = EchoSpan(0, 100, "")  # buffer was rewritten since
    editing_ui.output_field.text = "short"

    editing_ui.redraw_echo(entry)

    assert entry.echo_spans == {}


def test_redraw_echo_is_a_noop_without_span(editing_ui):
    # No span recorded (echo was confirmation-buffered) — nothing to splice.
    entry = make_entry()
    entry.echo_spans = {}
    editing_ui.output_field.text = "head"

    editing_ui.redraw_echo(entry)

    assert editing_ui.output_text == "head"
    assert entry.echo_spans == {}


def test_redraw_echo_renders_a_message_whose_text_is_markdown(editing_ui):
    # A merge whose combined text turned Markdown renders the WHOLE queued
    # message into the echo, and re-tracks the span so a later edit can still
    # rewrite the display.
    echo = "\n💬 10:00 >> hello\n"
    editing_ui.output_field.text = "head" + echo + "tail"
    entry = make_entry(text="hello\n- item")
    start = len("head")
    entry.echo_spans[editing_ui] = EchoSpan(start, start + len(echo), echo)

    with patch(
        "zrb.llm.ui.default.output.render_markdown",
        return_value="HELLO\n- ITEM",
    ) as mock_render:
        rewritten = editing_ui.redraw_echo(entry)

    # The full combined message — not `- item` alone — is what got rendered.
    assert mock_render.call_args.args[0] == "hello\n- item"
    assert editing_ui.output_text == "head" + "\n💬 10:00 >> HELLO\n- ITEM\n" + "tail"
    span = entry.echo_spans[editing_ui]
    assert span.start == start
    assert span.end == start + len("\n💬 10:00 >> HELLO\n- ITEM\n")
    assert span.text == "\n💬 10:00 >> HELLO\n- ITEM\n"
    assert rewritten == "\n💬 10:00 >> HELLO\n- ITEM\n"


def test_redraw_echo_renders_markdown_an_edit_introduced(editing_ui):
    """Render a queued message when an edit introduces Markdown."""
    echo = "\n💬 10:00 >> plain line\n"
    editing_ui.output_field.text = echo
    entry = make_entry(text="plain line")
    entry.echo_spans[editing_ui] = EchoSpan(0, len(echo), echo)

    entry.text = "# title"
    with patch(
        "zrb.llm.ui.default.output.render_markdown",
        return_value="TITLE",
    ) as mock_render:
        editing_ui.redraw_echo(entry)

    assert mock_render.call_args.args[0] == "# title"
    assert editing_ui.output_text == "\n💬 10:00 >> TITLE\n"


def test_redraw_echo_returns_to_raw_text_when_an_edit_drops_the_markdown(editing_ui):
    """Return a rendered echo to raw text after editing."""
    echo = "\n💬 10:00 >> hello\n"
    editing_ui.output_field.text = echo
    entry = make_entry(text="hello\n- item")
    entry.echo_spans[editing_ui] = EchoSpan(0, len(echo), echo)

    with patch(
        "zrb.llm.ui.default.output.render_markdown", return_value="HELLO\n- ITEM"
    ):
        editing_ui.redraw_echo(entry)
    entry.text = "just words"
    editing_ui.redraw_echo(entry)

    assert editing_ui.output_text == "\n💬 10:00 >> just words\n"
    # One block, covering the whole echo, and re-rendering to itself.
    assert len(editing_ui.rendered_blocks) == 1
    block = editing_ui.rendered_blocks[0]
    assert editing_ui.output_text[block[0] : block[1]] == "\n💬 10:00 >> just words\n"
    assert block[3](block[2], 40) == "\n💬 10:00 >> just words\n"


def test_redraw_echo_tracks_the_whole_echo_for_rewrap(editing_ui):
    """Track the whole rendered echo for resize reflow."""
    echo = "\n💬 10:00 >> hello\n"
    editing_ui.output_field.text = "head" + echo
    entry = make_entry(text="hello\n- item")
    start = len("head")
    entry.echo_spans[editing_ui] = EchoSpan(start, start + len(echo), echo)

    with patch("zrb.llm.ui.default.output.get_terminal_size") as mock_size:
        mock_size.return_value.columns = 60
        with patch(
            "zrb.llm.ui.default.output.render_markdown",
            side_effect=lambda text, width=None, theme=None: f"[{width}]{text}",
        ):
            editing_ui.redraw_echo(entry)
            assert "head\n💬 10:00 >> [56]hello\n- item\n" == editing_ui.output_text
            block = editing_ui.rendered_blocks[0]
            assert (
                editing_ui.output_text[block[0] : block[1]]
                == "\n💬 10:00 >> [56]hello\n- item\n"
            )

            mock_size.return_value.columns = 100
            editing_ui.rewrap_output()

    assert editing_ui.output_text == "head\n💬 10:00 >> [96]hello\n- item\n"


def test_echo_span_follows_a_rewrap_that_changed_the_rendered_length(editing_ui):
    """Keep the echo span valid after resize reflow."""
    echo = "\n💬 10:00 >> hello\n"
    editing_ui.output_field.text = echo
    entry = make_entry(text="hello\n- item")
    entry.echo_spans[editing_ui] = EchoSpan(0, len(echo), echo)

    with patch("zrb.llm.ui.default.output.get_terminal_size") as mock_size:
        mock_size.return_value.columns = 60
        with patch(
            "zrb.llm.ui.default.output.render_markdown",
            side_effect=lambda text, width=None, theme=None: f"[{width}]{text}",
        ):
            editing_ui.redraw_echo(entry)
            assert editing_ui.output_text == "\n💬 10:00 >> [56]hello\n- item\n"

            # Widening re-renders the echo one character longer ("[56]" ->
            # "[116]"), so every offset recorded before the resize is now off.
            mock_size.return_value.columns = 120
            editing_ui.rewrap_output()
            assert editing_ui.output_text == "\n💬 10:00 >> [116]hello\n- item\n"

            entry.text = "hello\n- item\n- more"
            rewritten = editing_ui.redraw_echo(entry)

    assert rewritten is not None
    assert editing_ui.output_text == "\n💬 10:00 >> [116]hello\n- item\n- more\n"


def test_echo_span_follows_an_in_place_edit_above_the_echo(editing_ui):
    """Rebase an echo after text above it changes length."""
    above = "tool output\n"
    echo = "\n💬 10:00 >> hello\n"
    editing_ui.output_field.text = above + echo
    entry = make_entry(text="hello")
    entry.echo_spans[editing_ui] = EchoSpan(len(above), len(above) + len(echo), echo)

    editing_ui.redraw_echo(entry)  # registers the echo's block
    editing_ui.replace_output_span(0, len(above), "a much longer tool output line\n")
    entry.text = "edited"
    rewritten = editing_ui.redraw_echo(entry)

    assert rewritten == "\n💬 10:00 >> edited\n"
    assert (
        editing_ui.output_text
        == "a much longer tool output line\n\n💬 10:00 >> edited\n"
    )


def test_redraw_echo_is_parked_while_a_sub_agent_transcript_is_displayed(editing_ui):
    """Defer redraw while the main transcript is parked."""
    echo = "\n💬 10:00 >> hello\n"
    editing_ui.output_field.text = echo
    entry = make_entry(text="hello")
    entry.echo_spans[editing_ui] = EchoSpan(0, len(echo), echo)
    editing_ui.redraw_echo(entry)

    sub_agent_transcript = "sub-agent output, nothing to do with the echo\n"
    editing_ui.output_field.text = sub_agent_transcript
    editing_ui.viewing_agent_id = "agent-1"
    entry.text = "edited"
    rewritten = editing_ui.redraw_echo(entry)

    assert rewritten is None
    assert editing_ui.output_text == sub_agent_transcript  # untouched
    # Kept, not pruned, and still addressing the parked transcript.
    assert (entry.echo_spans[editing_ui].start, entry.echo_spans[editing_ui].end) == (
        0,
        len(echo),
    )


def test_redraw_echo_drops_a_block_whose_offsets_left_the_echo(editing_ui):
    """Discard a block whose offsets no longer address its echo."""
    echo = "\n💬 10:00 >> hello\n"
    editing_ui.output_field.text = echo
    entry = make_entry(text="hello")
    entry.echo_spans[editing_ui] = EchoSpan(0, len(echo), echo)
    editing_ui.redraw_echo(entry)

    editing_ui.output_field.text = "completely different transcript of the same length"
    entry.text = "edited"
    rewritten = editing_ui.redraw_echo(entry)

    assert rewritten is None
    assert (
        editing_ui.output_text == "completely different transcript of the same length"
    )
    assert editing_ui.rendered_blocks == []
    assert entry.echo_spans == {}


def test_redraw_echo_rejects_a_block_that_drifted_onto_another_echo(editing_ui):
    """Reject a span that drifted onto another echo."""
    mine = "\n💬 10:00 >> hello\n"
    someone_elses = "\n💬 10:00 >> world\n"  # same length, same header
    editing_ui.output_field.text = mine
    entry = make_entry(text="hello")
    entry.echo_spans[editing_ui] = EchoSpan(0, len(mine), mine)
    editing_ui.redraw_echo(entry)

    editing_ui.output_field.text = someone_elses
    entry.text = "edited"
    rewritten = editing_ui.redraw_echo(entry)

    assert rewritten is None
    assert editing_ui.output_text == someone_elses  # untouched
    assert editing_ui.rendered_blocks == []
    assert entry.echo_spans == {}


def test_echo_block_does_not_keep_its_queued_message_alive(editing_ui):
    """Rendered blocks must not keep queued messages alive."""
    entry = make_entry(text="hello")
    entry.attachments.append("a-large-pasted-image")
    echo = "\n💬 10:00 >> hello\n"
    editing_ui.output_field.text = echo

    editing_ui.track_echo_span(entry, echo)
    assert len(editing_ui.rendered_blocks) == 1
    dead = weakref.ref(entry)
    del entry
    gc.collect()

    assert dead() is None
    # The block still re-renders the text it drew, from its own snapshot.
    block = editing_ui.rendered_blocks[0]
    assert block[3](block[2], 40) == echo


def test_track_echo_span_registers_the_first_echo_as_a_block(editing_ui):
    """Track the first echo before any redraw."""
    entry = make_entry(text="hello")
    echo = "\n💬 10:00 >> hello\n"
    editing_ui.output_field.text = "head" + echo

    editing_ui.track_echo_span(entry, echo)

    assert len(editing_ui.rendered_blocks) == 1
    block = editing_ui.rendered_blocks[0]
    assert editing_ui.output_text[block[0] : block[1]] == echo
    assert block[3](block[2], 40) == echo


def test_track_echo_span_skips_the_block_when_a_rerender_would_differ(editing_ui):
    """Skip block tracking when the redraw would differ from the visible echo."""
    entry = make_entry(text="hello")
    echo = "\n💬 10:00 >> something else entirely\n"
    editing_ui.output_field.text = echo

    editing_ui.track_echo_span(entry, echo)

    assert editing_ui.rendered_blocks == []
    # The span itself is still recorded — only the block is declined.
    assert entry.echo_spans[editing_ui].text == echo


def test_redraw_echo_replaces_its_own_block_instead_of_stacking_them(editing_ui):
    """Replace a redraw's block instead of stacking stale spans."""
    echo = "\n💬 10:00 >> hello\n"
    editing_ui.output_field.text = echo
    entry = make_entry(text="hello\n- item")
    entry.echo_spans[editing_ui] = EchoSpan(0, len(echo), echo)

    with patch(
        "zrb.llm.ui.default.output.render_markdown",
        side_effect=lambda text, width=None, theme=None: text.upper(),
    ):
        editing_ui.redraw_echo(entry)
        entry.text = "hello\n- item\n- more"
        editing_ui.redraw_echo(entry)

    assert len(editing_ui.rendered_blocks) == 1
    assert editing_ui.output_text == "\n💬 10:00 >> HELLO\n- ITEM\n- MORE\n"
