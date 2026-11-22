"""The audio device is written off for the whole process once a CoreAudio call
has been given up on, so every speech test starts with it written back in."""

import pytest

from zrb.llm.presentation.speech import feature, pcm_player
from zrb.llm.presentation.speech.repair import SpeechRepairError


@pytest.fixture
def lock_file(tmp_path):
    """A lock file of the test's own, so no two tests share one."""
    return str(tmp_path / "speech.lock")


@pytest.fixture(autouse=True)
def _device_is_not_wedged(monkeypatch):
    monkeypatch.setattr(pcm_player, "_device_wedged", False)


@pytest.fixture(autouse=True)
def _no_model_is_asked_for_a_repair(monkeypatch):
    """These tests drive hook paths, not models.

    A reply that missed its block is repaired by a small model in real use, so
    the default here is a repair that fails: every existing test then keeps
    seeing what it saw before the repair existed — the reply read whole. The
    repair's own tests replace this with a model of their own.
    """

    async def _no_model(*args, **kwargs):
        raise SpeechRepairError("a speech test asks no model")

    monkeypatch.setattr(feature, "repair_for_speech", _no_model)

