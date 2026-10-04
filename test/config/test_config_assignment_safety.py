import pytest

from zrb.config.config import Config


def test_assigning_an_unknown_uppercase_knob_raises_and_suggests():
    cfg = Config()
    with pytest.raises(AttributeError) as excinfo:
        cfg.LLM_MODELL = "oops"
    message = str(excinfo.value)
    assert "LLM_MODELL" in message
    assert "LLM_MODEL" in message  # the suggestion


def test_assigning_a_known_knob_still_works():
    cfg = Config()
    cfg.LLM_MODEL = "anthropic:claude-opus-5"
    assert cfg.LLM_MODEL == "anthropic:claude-opus-5"


def test_assigning_an_uncastable_value_raises_at_the_assignment():
    cfg = Config()
    with pytest.raises(ValueError) as excinfo:
        cfg.LLM_MAX_REQUEST_PER_MINUTE = "not-a-number"
    assert "LLM_MAX_REQUEST_PER_MINUTE" in str(excinfo.value)


def test_a_read_write_property_is_still_assignable():
    cfg = Config()
    cfg.ROOT_GROUP_NAME = "myproject"
    assert cfg.ROOT_GROUP_NAME == "myproject"


def test_get_settable_field_names_lists_known_knobs_only():
    cfg = Config()
    names = cfg.get_settable_field_names()
    assert "LLM_MODEL" in names
    assert "LLM_MAX_REQUEST_PER_MINUTE" in names
    assert not any(n.startswith("DEFAULT_") for n in names)


def test_convert_setting_value_casts_strings_to_field_types():
    cfg = Config()
    assert cfg.convert_setting_value("LLM_MAX_REQUEST_PER_MINUTE", "12") == 12
    assert cfg.convert_setting_value("LLM_SHOW_OLLAMA_MODELS", "on") is True
    assert cfg.convert_setting_value("LLM_MODEL", "my-model") == "my-model"


def test_convert_setting_value_unknown_name_raises_with_suggestion():
    cfg = Config()
    with pytest.raises(AttributeError) as excinfo:
        cfg.convert_setting_value("LLM_MODELL", "x")
    message = str(excinfo.value)
    assert "LLM_MODELL" in message
    assert "LLM_MODEL" in message


def test_convert_setting_value_uncastable_raises_naming_setting_and_value():
    cfg = Config()
    with pytest.raises(ValueError) as excinfo:
        cfg.convert_setting_value("LLM_MAX_REQUEST_PER_MINUTE", "nope")
    message = str(excinfo.value)
    assert "LLM_MAX_REQUEST_PER_MINUTE" in message
    assert "nope" in message


def test_convert_setting_value_applies_the_transform_a_read_would():
    """Converting must follow the same cast-then-transform path a read does.

    `BANNER`'s transform expands `{VERSION}`, and each token threshold is clamped
    against the rate limits by its transform. Converting with `cast` alone would
    hand `/set` a value the next read silently changes, so the command would
    store and confirm something other than the effective setting (round-5
    review).
    """
    cfg = Config()
    assert cfg.convert_setting_value("BANNER", "hi {VERSION}") == f"hi {cfg.VERSION}"
    threshold = cfg.convert_setting_value(
        "LLM_FILE_ANALYSIS_TOKEN_THRESHOLD", "999999999"
    )
    assert threshold <= cfg.LLM_MAX_TOKEN_PER_MINUTE
    assert threshold <= cfg.LLM_MAX_TOKEN_PER_REQUEST
