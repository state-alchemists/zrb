import asyncio

import pytest

from zrb.llm.custom_command import ActionCommand


class FakeUI:
    def __init__(self):
        self.background_tasks: set = set()
        self.outputs: list[str] = []

    def append_to_output(self, text: str) -> None:
        self.outputs.append(text)


def test_sync_action_reply_is_returned():
    cmd = ActionCommand("/hi", lambda kwargs, ui: "hello")
    assert cmd.handle({}, None) == "hello"


def test_sync_action_returning_none_shows_nothing():
    cmd = ActionCommand("/quiet", lambda kwargs, ui: None)
    assert cmd.handle({}, None) == ""


@pytest.mark.asyncio
async def test_async_action_runs_in_the_background_and_shows_its_reply():
    async def action(kwargs, ui):
        await asyncio.sleep(0)
        return "done"

    ui = FakeUI()
    assert ActionCommand("/slow", action).handle({}, ui) == ""
    assert len(ui.background_tasks) == 1

    await asyncio.gather(*ui.background_tasks)
    await asyncio.sleep(0)

    assert ui.background_tasks == set()
    assert any("done" in output for output in ui.outputs)


@pytest.mark.asyncio
async def test_async_action_failure_is_shown():
    async def action(kwargs, ui):
        raise RuntimeError("camera on fire")

    ui = FakeUI()
    ActionCommand("/boom", action).handle({}, ui)
    await asyncio.gather(*ui.background_tasks, return_exceptions=True)
    await asyncio.sleep(0)

    assert any("camera on fire" in output for output in ui.outputs)


@pytest.mark.asyncio
async def test_cancelled_async_action_shows_nothing():
    async def action(kwargs, ui):
        await asyncio.sleep(10)

    ui = FakeUI()
    ActionCommand("/wait", action).handle({}, ui)
    for task in ui.background_tasks:
        task.cancel()
    await asyncio.gather(*ui.background_tasks, return_exceptions=True)
    await asyncio.sleep(0)

    assert ui.outputs == []


def test_async_action_without_a_ui_is_refused_and_never_runs():
    ran = []

    async def action(kwargs, ui):
        ran.append(1)

    reply = ActionCommand("/photo", action).handle({}, None)

    assert "interactive" in reply
    assert ran == []


def test_can_run_while_thinking_defaults_to_false():
    assert ActionCommand("/x", lambda kwargs, ui: None).can_run_while_thinking is False
    cmd = ActionCommand("/x", lambda kwargs, ui: None, can_run_while_thinking=True)
    assert cmd.can_run_while_thinking is True


def test_arg_completions_come_from_complete_arg():
    cmd = ActionCommand(
        "/pick",
        lambda kwargs, ui: None,
        args=["item"],
        complete_arg=lambda prefix: [
            v for v in ("apple", "avocado") if v.startswith(prefix)
        ],
    )
    assert cmd.get_arg_completions("av") == ["avocado"]
    assert ActionCommand("/x", lambda kwargs, ui: None).get_arg_completions("") == []
