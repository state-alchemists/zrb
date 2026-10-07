from zrb.llm.dictation.config import DictationConfig


def test_barge_in_hold_does_not_shift_legacy_positional_fields():
    config = DictationConfig(
        "mode",
        [],
        [],
        "backend",
        [],
        5,
        6,
        7,
        8,
        9,
        10,
        11,
        12,
        13,
        14,
        True,
        16,
        17,
        18,
        True,
    )

    assert config.barge_in_enabled is True
    assert config.barge_in_min_speech == 16
    assert config.barge_in_margin == 17
    assert config.barge_in_min_words == 18
    assert config.interrupt_judge_enabled is True
    assert config.barge_in_hold is None
