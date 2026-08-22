"""Tests for run-setup dependency resolution (yolo inheritance semantics)."""

from zrb.llm.agent.run.runtime_state import current_yolo
from zrb.llm.agent.run.setup import _resolve_context_dependencies


def test_yolo_none_inherits_parent_context():
    token = current_yolo.set(True)
    try:
        _, _, effective_yolo, _, _ = _resolve_context_dependencies(
            None, None, None, None, None
        )
        assert effective_yolo is True
    finally:
        current_yolo.reset(token)


def test_yolo_explicit_false_stays_false():
    """An explicit False must opt out of an inherited YOLO context."""
    token = current_yolo.set(True)
    try:
        _, _, effective_yolo, _, _ = _resolve_context_dependencies(
            None, None, False, None, None
        )
        assert effective_yolo is False
    finally:
        current_yolo.reset(token)


def test_yolo_explicit_true_wins_over_unyolo_parent():
    _, _, effective_yolo, _, _ = _resolve_context_dependencies(
        None, None, True, None, None
    )
    assert effective_yolo is True


def test_yolo_defaults_to_false_without_context():
    _, _, effective_yolo, _, _ = _resolve_context_dependencies(
        None, None, None, None, None
    )
    assert effective_yolo is False
