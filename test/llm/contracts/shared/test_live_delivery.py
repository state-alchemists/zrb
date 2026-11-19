"""Reaching into a run that is already executing (ADR-0078)."""

from unittest.mock import MagicMock

from pydantic_ai.messages import UserContent

from zrb.llm.contracts.shared.live_delivery import steer_into_live_run


def test_steer_into_live_run_false_without_active_run():
    assert steer_into_live_run(None, "hello", []) is False


def test_steer_into_live_run_delivers_via_enqueue():
    run_context = MagicMock()
    attachments: list[UserContent] = ["image-bytes"]

    assert steer_into_live_run(run_context, "hello", attachments) is True

    run_context.enqueue.assert_called_once_with("hello", "image-bytes", priority="asap")


def test_steer_into_live_run_false_when_enqueue_raises():
    run_context = MagicMock()
    run_context.enqueue.side_effect = RuntimeError("run already finished")

    assert steer_into_live_run(run_context, "hello", []) is False
