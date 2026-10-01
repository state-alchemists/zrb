"""Every voice setting is a `CFG` knob, a `DictationConfig`/`SpeechConfig`
field read from it when a session starts (so `zrb_init.py` can change it),
and a row in docs/configuration/llm-config.md."""

from dataclasses import fields
from pathlib import Path

import pytest

from zrb.config.config import CFG
from zrb.config.env_field import EnvField
from zrb.llm.dictation.config import DictationConfig
from zrb.llm.speech.config import SpeechConfig

_DOC = Path(__file__).parents[2] / "docs" / "configuration" / "llm-config.md"
_FEATURES = [("LLM_DICTATION_", DictationConfig), ("LLM_SPEECH_", SpeechConfig)]


def _knobs(prefix: str) -> set[str]:
    return {
        name
        for klass in type(CFG).__mro__
        for name, value in vars(klass).items()
        if name.startswith(prefix) and isinstance(value, EnvField)
    }


@pytest.mark.parametrize("prefix, config", _FEATURES)
def test_every_knob_is_a_config_field_and_every_field_a_knob(prefix, config):
    knobs = {name[len(prefix) :].lower() for name in _knobs(prefix)}
    assert {field.name for field in fields(config)} == knobs


@pytest.mark.parametrize("prefix", [prefix for prefix, _ in _FEATURES])
def test_every_knob_is_documented(prefix):
    doc = _DOC.read_text()
    missing = sorted(name for name in _knobs(prefix) if f"`ZRB_{name}`" not in doc)
    assert missing == [], f"add these to {_DOC.name}: {missing}"


@pytest.mark.parametrize(
    "config, knob, value, field",
    [
        (DictationConfig, "LLM_DICTATION_STOP_WORDS", "berhenti", "stop_words"),
        (
            SpeechConfig,
            "LLM_SPEECH_QUESTION_MESSAGE",
            "Ada pertanyaan.",
            "question_message",
        ),
    ],
)
def test_a_knob_changed_after_the_config_is_made_is_what_a_session_reads(
    config, knob, value, field, monkeypatch
):
    made = config()  # as enable_* is called, when zrb is imported
    monkeypatch.setenv(f"{CFG.ENV_PREFIX}_{knob}", value)  # then zrb_init.py
    resolved = getattr(made.resolve(), field)
    assert resolved == ([value] if isinstance(resolved, list) else value)
