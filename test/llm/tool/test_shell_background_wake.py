"""A background command that ends tells the session that started it.

The registry outlives any turn and holds the only copy of the ending, so the
ending has to be pushed to the UI of the run that started the command: with
nobody typing, nothing else will look.
"""

import asyncio

import pytest

from zrb.config.config import CFG
from zrb.llm.agent_state import current_ui
from zrb.llm.input_source import BACKGROUND_INPUT
from zrb.llm.tool.shell_background import get_shell_background_registry


class _RecordingUI:
    """Stands in for the UI of the run: records what it was asked to queue."""

    def __init__(self, fails_with: Exception | None = None):
        self.messages: list[tuple[str, object]] = []
        self.withdrawn: list[tuple[str, object]] = []
        self._fails_with = fails_with

    def submit_message(self, user_message, source):
        if self._fails_with is not None:
            raise self._fails_with
        self.messages.append((user_message, source))

    def withdraw_message(self, user_message, source):
        self.withdrawn.append((user_message, source))


@pytest.fixture
def ui():
    recording = _RecordingUI()
    token = current_ui.set(recording)  # type: ignore[arg-type]
    yield recording
    current_ui.reset(token)


async def _until(predicate, seconds: float = 10.0):
    for _ in range(int(seconds / 0.02)):
        if predicate():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("condition not reached")


@pytest.mark.asyncio
async def test_the_session_is_told_when_a_background_command_ends(ui):
    registry = get_shell_background_registry()

    handle = await registry.start("echo SECRET-OUTPUT; exit 3", "", "Failing job")
    await _until(lambda: ui.messages)

    ((message, source),) = ui.messages
    assert source == BACKGROUND_INPUT
    assert f"Background process {handle} finished (exit 3): Failing job" in message
    assert f"MonitorProcess(handle='{handle}')" in message
    assert "SECRET-OUTPUT" not in message  # a pointer, never the output
    await registry.collect(handle, wait=10)


@pytest.mark.asyncio
async def test_a_command_that_is_still_running_has_told_nobody(ui):
    registry = get_shell_background_registry()

    handle = await registry.start("sleep 30", "", "Long job")
    await asyncio.sleep(0.2)

    assert ui.messages == []
    await registry.kill(handle)


@pytest.mark.asyncio
async def test_a_stop_somebody_asked_for_is_not_reported(ui):
    registry = get_shell_background_registry()

    handle = await registry.start("sleep 30", "", "Killed by the model")
    await registry.kill(handle)
    await asyncio.sleep(0.3)

    assert ui.messages == []


@pytest.mark.asyncio
async def test_a_shutdown_is_not_reported(ui):
    registry = get_shell_background_registry()

    await registry.start("sleep 30", "", "Stopped with the session")
    await registry.cancel_all()
    await asyncio.sleep(0.3)

    assert ui.messages == []


@pytest.mark.asyncio
async def test_a_command_someone_is_waiting_on_is_reported_by_that_wait(ui):
    registry = get_shell_background_registry()

    handle = await registry.start("sleep 0.5", "", "Awaited")
    result = await registry.collect(handle, wait=10)

    assert "exited (code 0)" in result
    assert ui.messages == []


@pytest.mark.asyncio
async def test_a_handle_the_model_already_consumed_is_not_reported(ui):
    registry = get_shell_background_registry()

    handle = await registry.start("sleep 0.3", "", "Consumed first")
    await registry.collect(handle, wait=10)
    await asyncio.sleep(0.2)

    assert ui.messages == []


@pytest.mark.asyncio
async def test_the_knob_turns_the_wake_up_off(ui, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_BACKGROUND_WAKE", False)
    registry = get_shell_background_registry()

    handle = await registry.start("exit 0", "", "Quiet")
    await registry.collect(handle, wait=10)
    await asyncio.sleep(0.2)

    assert ui.messages == []


@pytest.mark.asyncio
async def test_a_run_with_no_ui_has_nobody_to_tell():
    registry = get_shell_background_registry()

    handle = await registry.start("exit 0", "", "Headless")
    result = await registry.collect(handle, wait=10)

    assert "exited (code 0)" in result


@pytest.mark.asyncio
async def test_a_ui_that_cannot_take_the_message_costs_the_nudge_only():
    failing = _RecordingUI(fails_with=RuntimeError("the UI is closing"))
    token = current_ui.set(failing)  # type: ignore[arg-type]
    try:
        registry = get_shell_background_registry()
        handle = await registry.start("exit 4", "", "Nobody home")
        await asyncio.sleep(0.5)
        result = registry.poll(handle)
    finally:
        current_ui.reset(token)

    assert "exited (code 4)" in result


@pytest.mark.asyncio
async def test_a_command_stopped_at_its_deadline_is_reported(ui, monkeypatch):
    """Nobody asked for that stop; it is how the process's time ended."""
    monkeypatch.setattr(CFG, "LLM_SHELL_TIMEOUT_BACKGROUND_SECONDS", 1)
    registry = get_shell_background_registry()
    process = await asyncio.create_subprocess_exec(
        "sleep",
        "30",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    from zrb.llm.tool.stream_capture import StreamCapture

    handle = await registry.adopt(
        process, "sleep 30", StreamCapture(1000, 0), StreamCapture(1000, 0)
    )
    await _until(lambda: ui.messages)

    ((message, _),) = ui.messages
    assert f"Background process {handle} finished" in message
    await registry.cancel_all()


@pytest.mark.asyncio
async def test_a_command_line_is_not_put_in_the_transcript_unless_described(ui):
    """With no description the command line is all there is, and it can hold a
    credential; the wake-up lands in the transcript, so it names nothing."""
    registry = get_shell_background_registry()

    handle = await registry.start("sleep 0.1 # Bearer SECRET-TOKEN", "", "")
    await _until(lambda: ui.messages)

    ((message, _),) = ui.messages
    assert "SECRET-TOKEN" not in message
    assert f"Background process {handle} finished (exit 0)." in message
    await registry.collect(handle, wait=10)


@pytest.mark.asyncio
async def test_a_description_the_caller_wrote_is_named(ui):
    registry = get_shell_background_registry()

    await registry.start("exit 0", "", "Nightly build")
    await _until(lambda: ui.messages)

    assert "Nightly build" in ui.messages[0][0]


@pytest.mark.asyncio
async def test_consuming_the_handle_takes_back_a_wake_up_still_queued(ui):
    """The model reading the ending makes the nudge moot: left queued it would
    start a turn about a handle that no longer exists."""
    registry = get_shell_background_registry()

    handle = await registry.start("exit 0", "", "Read before the nudge ran")
    await _until(lambda: ui.messages)
    ((message, _),) = ui.messages

    for _ in range(100):
        if "consumed" in registry.poll(handle):
            break
        await asyncio.sleep(0.02)

    assert ui.withdrawn == [(message, BACKGROUND_INPUT)]


@pytest.mark.asyncio
async def test_nothing_is_withdrawn_when_nothing_was_sent(ui, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_BACKGROUND_WAKE", False)
    registry = get_shell_background_registry()

    handle = await registry.start("exit 0", "", "No wake-up")
    await registry.collect(handle, wait=10)

    assert ui.withdrawn == []


@pytest.mark.asyncio
async def test_a_process_that_exits_as_its_deadline_fires_is_reported_once(
    ui, monkeypatch
):
    """The exit wait and the deadline stop both notice an ending; the session is
    told once. The stop is made to let the exit wait run first, which is the
    order the race produces."""
    import zrb.llm.tool.shell_background as module
    from zrb.llm.tool.stream_capture import StreamCapture

    async def stop_after_the_exit_was_heard(bp):
        bp.process.kill()
        await bp.process.wait()
        for _ in range(5):
            await asyncio.sleep(0)

    monkeypatch.setattr(module, "_stop_process", stop_after_the_exit_was_heard)
    monkeypatch.setattr(CFG, "LLM_SHELL_TIMEOUT_BACKGROUND_SECONDS", 1)
    registry = get_shell_background_registry()
    process = await asyncio.create_subprocess_exec(
        "sleep",
        "30",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )

    await registry.adopt(
        process, "sleep 30", StreamCapture(1000, 0), StreamCapture(1000, 0)
    )
    await _until(lambda: ui.messages)
    await asyncio.sleep(0.5)

    assert len(ui.messages) == 1
