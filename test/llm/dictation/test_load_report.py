"""A model's loading line is followed by a ready or a failure line."""

import logging

import pytest

from zrb.llm.dictation.load_report import prepare_reported


class FakeUI:
    def __init__(self):
        self.outputs: list[str] = []

    def append_to_output(self, text):
        self.outputs.append(text)


def _loading(error: Exception | None = None):
    async def prepare(report):
        report("Loading the model…")
        if error is not None:
            raise error

    return prepare


async def _loaded(report):
    pass


@pytest.mark.asyncio
async def test_a_load_ends_with_a_ready_line():
    ui = FakeUI()

    await prepare_reported("sensevoice", _loading(), lambda: ui)

    assert len(ui.outputs) == 2
    assert "🎤 Loading the model…" in ui.outputs[0]
    assert "✅ sensevoice ready" in ui.outputs[1]


@pytest.mark.asyncio
async def test_a_model_already_loaded_says_nothing():
    ui = FakeUI()

    await prepare_reported("sensevoice", _loaded, lambda: ui)

    assert ui.outputs == []


@pytest.mark.asyncio
async def test_a_load_that_raises_ends_with_a_failure_line_and_raises():
    ui = FakeUI()

    with pytest.raises(RuntimeError, match="no sherpa"):
        await prepare_reported(
            "sensevoice", _loading(RuntimeError("no sherpa")), lambda: ui
        )

    assert "❗ sensevoice failed to load: no sherpa" in ui.outputs[-1]
    assert not any("✅" in output for output in ui.outputs)


@pytest.mark.asyncio
async def test_a_failure_reported_after_the_load_ends_with_a_failure_line():
    ui = FakeUI()

    await prepare_reported("emotion model", _loading(), lambda: ui, lambda: "no funasr")

    assert "❗ emotion model failed to load: no funasr" in ui.outputs[-1]


@pytest.mark.asyncio
async def test_a_silent_failure_without_an_announced_load_says_nothing():
    ui = FakeUI()

    with pytest.raises(RuntimeError):
        await prepare_reported("vosk", _raising(RuntimeError("offline")), lambda: ui)

    assert ui.outputs == []


@pytest.mark.asyncio
async def test_without_a_ui_the_lines_are_logged(caplog):
    with caplog.at_level(logging.WARNING):
        await prepare_reported("vosk", _loading(), lambda: None)

    assert "Loading the model…" in caplog.text
    assert "✅ vosk ready" in caplog.text


def _raising(error: Exception):
    async def prepare(report):
        raise error

    return prepare
