"""`BaseUI.trigger_loop`: how items a trigger yields become turns or answers."""

import asyncio
from unittest.mock import MagicMock

import pytest

from zrb.context.context import Context
from zrb.context.shared_context import SharedContext
from zrb.llm.ui.base.ui import BaseUI
from zrb.llm.ui.trigger import TriggerMessage, TriggerReply


class ConcreteUI(BaseUI):
    def append_to_output(self, *values, sep=" ", end="\n", kind="text", **kwargs):
        pass

    async def ask_user(self, prompt: str) -> str:
        return "yes"

    async def run_interactive_command(self, cmd, shell=False):
        return 0

    async def run_async(self) -> str:
        return self.last_output


class AnsweringUI(ConcreteUI):
    """A UI holding a pending question, recording what answers it."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.waiting = True
        self.answers: list[str] = []

    @property
    def is_waiting_for_answer(self) -> bool:
        return self.waiting

    def submit_answer(self, text: str) -> None:
        self.answers.append(text)


def _create_ui(ui_class=ConcreteUI):
    ctx = Context(SharedContext(), "test", 0, "")
    return ui_class(ctx=ctx, llm_task=MagicMock(), history_manager=MagicMock())


@pytest.fixture
def base_ui():
    return _create_ui()


# --- trigger_loop ------------------------------------------------------------


def collect_submitted(ui, monkeypatch):
    """Record `(text, drained_attachments)` per `submit_user_message` call."""
    submitted = []

    def fake_submit(llm_task, user_message):
        submitted.append((user_message, ui.take_pending_attachments()))

    monkeypatch.setattr(ui, "submit_user_message", fake_submit)
    return submitted


def trigger_yielding(*items):
    async def factory():
        for item in items:
            yield item

    return factory


@pytest.mark.asyncio
async def test_trigger_loop_submits_plain_strings(base_ui, monkeypatch):
    submitted = collect_submitted(base_ui, monkeypatch)

    await base_ui.trigger_loop(trigger_yielding("hello", "world"))

    assert submitted == [("hello", []), ("world", [])]


@pytest.mark.asyncio
async def test_trigger_loop_attaches_trigger_message_attachments(base_ui, monkeypatch):
    submitted = collect_submitted(base_ui, monkeypatch)
    photo = object()

    await base_ui.trigger_loop(
        trigger_yielding(TriggerMessage(text="what is this?", attachments=[photo]))
    )

    assert submitted == [("what is this?", [photo])]


@pytest.mark.asyncio
async def test_trigger_loop_accepts_a_bare_tuple(base_ui, monkeypatch):
    """A `(text, attachments)` tuple needs no `TriggerMessage` import."""
    submitted = collect_submitted(base_ui, monkeypatch)

    await base_ui.trigger_loop(trigger_yielding(("look", ["/tmp/shot.jpg"])))

    assert submitted == [("look", ["/tmp/shot.jpg"])]


@pytest.mark.asyncio
async def test_trigger_loop_submits_attachments_without_text(base_ui, monkeypatch):
    submitted = collect_submitted(base_ui, monkeypatch)
    photo = object()

    await base_ui.trigger_loop(trigger_yielding(TriggerMessage(attachments=[photo])))

    assert submitted == [("", [photo])]


@pytest.mark.asyncio
async def test_trigger_loop_skips_empty_items(base_ui, monkeypatch):
    """Silence from a voice trigger, and an explicit empty `TriggerMessage`."""
    submitted = collect_submitted(base_ui, monkeypatch)

    await base_ui.trigger_loop(
        trigger_yielding("", None, TriggerMessage(), ("", []), "kept")
    )

    assert submitted == [("kept", [])]


@pytest.mark.asyncio
async def test_trigger_loop_does_not_leak_attachments_between_items(
    base_ui, monkeypatch
):
    submitted = collect_submitted(base_ui, monkeypatch)
    photo = object()

    await base_ui.trigger_loop(
        trigger_yielding(TriggerMessage("first", [photo]), "second")
    )

    assert submitted == [("first", [photo]), ("second", [])]


@pytest.mark.asyncio
async def test_trigger_loop_unstages_attachments_when_submission_fails(
    base_ui, monkeypatch
):
    """A failed submission must not leave its attachments for the next turn.

    `submit_user_message` drains `pending_attachments` only after echoing the
    message, so a raise before that point leaves them staged — and the next
    message, typed or triggered, would carry a photo nobody asked it to.
    """
    photo = object()

    def failing_submit(llm_task, user_message):
        raise RuntimeError("backend down")

    monkeypatch.setattr(base_ui, "submit_user_message", failing_submit)

    await base_ui.trigger_loop(trigger_yielding(TriggerMessage("look", [photo])))

    assert base_ui.pending_attachments == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "item",
    [("text", "one-path.png"), ("text", 3), ("a", ["x"], "extra"), ("only",)],
)
async def test_trigger_loop_reports_a_malformed_tuple_and_keeps_going(
    base_ui, monkeypatch, item
):
    """One bad item must not end the loop.

    A trigger is a long-lived source — a button, a queue — so aborting on the
    first malformed item silently stops every later one. A bare string in the
    attachments slot used to become a list of its characters, a 3-tuple lost
    its third element, and a non-sequence raised out of `list()`.
    """
    submitted = collect_submitted(base_ui, monkeypatch)
    reported: list[str] = []
    monkeypatch.setattr(
        base_ui,
        "append_to_output",
        lambda *v, **k: reported.append(" ".join(map(str, v))),
    )

    await base_ui.trigger_loop(trigger_yielding(item, "after"))

    assert submitted == [("after", [])]
    assert any("Trigger Error" in line for line in reported), reported


@pytest.mark.asyncio
async def test_trigger_loop_reads_none_attachments_as_none(base_ui, monkeypatch):
    """`(text, None)` is text with no attachments, like `TriggerMessage`'s default."""
    submitted = collect_submitted(base_ui, monkeypatch)

    await base_ui.trigger_loop(trigger_yielding(("hello", None)))

    assert submitted == [("hello", [])]


@pytest.mark.asyncio
async def test_trigger_reply_answers_the_pending_question(monkeypatch):
    ui = _create_ui(AnsweringUI)
    submitted = collect_submitted(ui, monkeypatch)

    await ui.trigger_loop(trigger_yielding(TriggerReply("yes")))

    assert ui.answers == ["yes"]
    assert submitted == []


@pytest.mark.asyncio
async def test_trigger_reply_is_a_turn_when_nothing_is_pending(monkeypatch):
    ui = _create_ui(AnsweringUI)
    ui.waiting = False
    submitted = collect_submitted(ui, monkeypatch)

    await ui.trigger_loop(trigger_yielding(TriggerReply("open the file")))

    assert ui.answers == []
    assert submitted == [("open the file", [])]


@pytest.mark.asyncio
async def test_an_empty_trigger_reply_never_answers(monkeypatch):
    """An empty answer approves a tool call, so it must never be sent."""
    ui = _create_ui(AnsweringUI)
    submitted = collect_submitted(ui, monkeypatch)

    await ui.trigger_loop(trigger_yielding(TriggerReply(""), TriggerReply("   ")))

    assert ui.answers == []
    assert submitted == []


@pytest.mark.asyncio
async def test_a_plain_string_never_answers_a_pending_question(monkeypatch):
    """Only a TriggerReply may answer: a scheduled or remote trigger must not
    be able to approve a tool call."""
    ui = _create_ui(AnsweringUI)
    submitted = collect_submitted(ui, monkeypatch)

    await ui.trigger_loop(trigger_yielding("yes"))

    assert ui.answers == []
    assert submitted == [("yes", [])]


def test_base_ui_holds_no_pending_answer_and_submits_instead(base_ui, monkeypatch):
    sent = []
    monkeypatch.setattr(base_ui, "submit_message", sent.append)

    assert base_ui.is_waiting_for_answer is False
    base_ui.submit_answer("yes")
    base_ui.insert_input_text("draft")

    assert sent == ["yes", "draft"]
