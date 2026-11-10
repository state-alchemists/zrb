"""The audio device is written off for the whole process once a CoreAudio call
has been given up on, so every speech test starts with it written back in."""

import pytest

from zrb.llm.speech import pcm_player


@pytest.fixture(autouse=True)
def _device_is_not_wedged(monkeypatch):
    monkeypatch.setattr(pcm_player, "_device_wedged", False)
