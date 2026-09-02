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
