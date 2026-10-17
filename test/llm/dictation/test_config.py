from dataclasses import fields

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


def test_a_field_added_after_barge_in_hold_leaves_every_earlier_position_alone():
    names = [field.name for field in fields(DictationConfig)]

    # `barge_in_hold` was the last field when the dataclass was last extended;
    # a later one goes after it, so a positional caller keeps its meaning.
    assert names.index("barge_in_hold") == 41
    assert names[names.index("barge_in_hold") + 1 :] == [
        "interrupt_judge_timeout",
        "interrupt_judge_max_words",
        "hush_words",
        "enable_echo_cancel",
        "detect_emotion",
        "sensevoice_model",
        "sensevoice_threads",
        "emotion_model",
        "emotion_min_score",
    ]
    assert names.index("interrupt_judge_model") == 20
