"""Pasting into the prompt: where the bytes land, and what they attach.

Two ways in, pinned here. `Ctrl-V` reads the system clipboard for an image and
refuses one too large to decode safely. A bracketed paste arrives from the
terminal as a single event and can carry a file path, a PDF or plain text: a
path attaches, an unreadable file or a second copy of an already-attached image
is reported instead of silently added, and text lands in the input field even
while focus sits on the read-only output pane. Neither path is allowed to leak
a paste into the buffer that had focus.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from prompt_toolkit.key_binding import KeyBindings

from .keybindings_support import MockUI, create_mock_event, trigger_binding


@pytest.fixture
def mock_ui():
    return MockUI()


@pytest.fixture
def key_bindings():
    return KeyBindings()


@pytest.fixture
def setup_bindings(mock_ui, key_bindings):
    llm_task = MagicMock()
    mock_ui.setup_app_keybindings(key_bindings, llm_task)
    return key_bindings


@pytest.mark.asyncio
async def test_ctrl_v_no_image_no_hint(mock_ui, setup_bindings):
    event = create_mock_event()

    with patch(
        "zrb.util.clipboard.get_clipboard_image", new_callable=AsyncMock
    ) as mock_get_img:
        with patch("zrb.util.clipboard.missing_tool_hint") as mock_hint:
            with patch("prompt_toolkit.application.get_app") as mock_get_app:
                mock_get_img.return_value = None
                mock_hint.return_value = None

                app_mock = MagicMock()
                mock_get_app.return_value = app_mock

                trigger_binding(setup_bindings, "c-v", event)

                # Wait for background task
                assert len(mock_ui.background_tasks) == 1
                await list(mock_ui.background_tasks)[0]

                app_mock.layout.focus.assert_called_with(mock_ui.input_field)
                mock_ui.input_field.buffer.paste_clipboard_data.assert_called_with(
                    "pasted_text"
                )


@pytest.mark.asyncio
async def test_ctrl_v_refuses_an_image_too_large_to_decode(
    mock_ui, setup_bindings, monkeypatch
):
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (20, 20), "red").save(buf, format="PNG")
    monkeypatch.setattr("zrb.llm.contracts.util.image_scale.MAX_DECODE_PIXELS", 100)
    with patch(
        "zrb.util.clipboard.get_clipboard_image", new_callable=AsyncMock
    ) as mock_get_img:
        mock_get_img.return_value = buf.getvalue()
        trigger_binding(setup_bindings, "c-v", create_mock_event())
        await list(mock_ui.background_tasks)[0]

    assert mock_ui.pending_attachments == []
    assert any("too large to decode safely" in out for out in mock_ui.outputs)


def _paste(key_bindings, data):
    # lazy: heavy third-party
    from prompt_toolkit.keys import Keys

    event = create_mock_event()
    event.data = data
    trigger_binding(key_bindings, Keys.BracketedPaste, event)
    return event


def test_bracketed_paste_of_a_file_path_attaches_it(mock_ui, setup_bindings, tmp_path):
    image = tmp_path / "pasted-image.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")

    _paste(setup_bindings, f"{image}\r\n")

    mock_ui.input_field.buffer.insert_text.assert_not_called()
    assert len(mock_ui.pending_attachments) == 1
    assert mock_ui.pending_attachments[0].media_type == "image/png"
    assert any("Attached: pasted-image.png" in o for o in mock_ui.outputs)


def test_bracketed_paste_of_an_unreadable_file_reports_it(
    mock_ui, setup_bindings, tmp_path
):
    image = tmp_path / "fake.png"
    image.write_bytes(b"not a png")

    _paste(setup_bindings, str(image))

    mock_ui.input_field.buffer.insert_text.assert_not_called()
    assert mock_ui.pending_attachments == []
    assert any("doesn't look like image/png" in o for o in mock_ui.outputs)


def test_bracketed_paste_of_text_goes_to_the_input_field(mock_ui, setup_bindings):
    # Focus may be on the read-only output pane; the paste still lands in input.
    event = _paste(setup_bindings, "line one\r\nline two\r")

    event.app.layout.focus.assert_called_once_with(mock_ui.input_field)
    mock_ui.input_field.buffer.insert_text.assert_called_once_with(
        "line one\nline two\n"
    )
    event.current_buffer.insert_text.assert_not_called()
    assert mock_ui.pending_attachments == []


def test_bracketed_paste_of_a_pdf_reaches_the_prompt_as_its_text(
    mock_ui, setup_bindings, tmp_path
):
    from zrb.llm.engine.agent.run.prompt_content import get_prompt_content

    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    mock_ui.submit_attachment = MagicMock(
        side_effect=mock_ui.pending_attachments.append
    )

    _paste(setup_bindings, str(pdf))
    with patch(
        "zrb.llm.contracts.util.attachment.extract_pdf_text", return_value="report text"
    ):
        content = get_prompt_content("hi", mock_ui.pending_attachments, print)

    mock_ui.submit_attachment.assert_called_once_with(str(pdf))
    assert content == ["hi", "report text"]


def test_bracketed_paste_of_the_same_image_twice_attaches_it_once(
    mock_ui, setup_bindings, tmp_path
):
    image = tmp_path / "pasted-image.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")

    _paste(setup_bindings, str(image))
    _paste(setup_bindings, str(image))

    assert len(mock_ui.pending_attachments) == 1
    assert any("Already attached: pasted-image.png" in o for o in mock_ui.outputs)


def test_bracketed_paste_of_an_image_queued_by_attach_is_not_added(
    mock_ui, setup_bindings, tmp_path
):
    image = tmp_path / "photo.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")
    mock_ui.pending_attachments.append(str(image))

    _paste(setup_bindings, str(image))

    assert mock_ui.pending_attachments == [str(image)]
    assert any("Already attached: photo.png" in o for o in mock_ui.outputs)
