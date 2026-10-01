import pytest

from zrb.config.config import Config


@pytest.mark.parametrize(
    "preset, speech, mode, barge_in",
    [
        ("off", False, "ptt", False),
        ("speak", True, "ptt", False),
        ("turns", True, "hands_free", False),
        ("conversation", True, "hands_free", True),
    ],
)
def test_a_voice_preset_sets_how_a_session_talks(
    monkeypatch, preset, speech, mode, barge_in
):
    monkeypatch.setenv("ZRB_LLM_VOICE", preset)
    cfg = Config()
    assert cfg.LLM_SPEECH_ENABLED is speech
    assert cfg.LLM_DICTATION_MODE == mode
    assert cfg.LLM_DICTATION_BARGE_IN_ENABLED is barge_in


def test_a_setting_set_on_its_own_wins_over_the_preset(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_VOICE", "conversation")
    monkeypatch.setenv("ZRB_LLM_DICTATION_BARGE_IN_ENABLED", "off")
    assert Config().LLM_DICTATION_BARGE_IN_ENABLED is False


def test_without_a_preset_each_setting_keeps_its_own_default(monkeypatch):
    monkeypatch.delenv("ZRB_LLM_VOICE", raising=False)
    cfg = Config()
    cfg.DEFAULT_LLM_SPEECH_ENABLED = "on"
    assert cfg.LLM_SPEECH_ENABLED is True


def test_an_unknown_preset_names_the_valid_ones(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_VOICE", "chatty")
    with pytest.raises(ValueError, match="off, speak, turns, conversation"):
        Config().LLM_SPEECH_ENABLED


def test_a_preset_is_spelled_either_way(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_VOICE", "Conversation")
    assert Config().LLM_VOICE == "conversation"
