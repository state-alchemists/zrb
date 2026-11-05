"""Every on/off setting names itself a switch: it ends in `_ENABLED`.

`LLM_ENABLE_REWIND` reads as an instruction and `LLM_BACKGROUND_WAKE` as a
value; both are booleans like `LLM_REWIND_ENABLED`, and the three shapes
coexisted long enough that picking one by eye was guesswork. The suffix is the
rule now, and the names below are the only settings exempt from it: a predicate
and two modes, where the name is the thing itself rather than a switch.
"""

from zrb.config.config import Config
from zrb.config.env_field import EnvField

#: Booleans that are not switches: a question, and two modes whose name is the
#: choice itself (`LLM_SPEECH_STREAM` streams or reads whole; `BARGE_IN_HOLD`
#: holds or cuts). `_ENABLED` would say nothing on top of either.
NOT_A_SWITCH = frozenset(
    {
        "IS_TERMUX",
        "LLM_SPEECH_STREAM",
        "LLM_DICTATION_BARGE_IN_HOLD",
    }
)


def _boolean_fields() -> list[str]:
    return sorted(
        name
        for klass in type(Config).__mro__
        for name, value in vars(klass).items()
        if isinstance(value, EnvField) and value.is_boolean
    )


def test_every_boolean_setting_is_named_a_switch():
    offenders = [name for name in _boolean_fields() if not name.endswith("_ENABLED")]
    assert offenders == [], (
        "A boolean setting must end in `_ENABLED`; if it is a predicate or a "
        "mode rather than a switch, add it to NOT_A_SWITCH with the reason."
    )


def test_a_switch_is_not_named_for_what_it_turns_off():
    """`_DISABLED` inverts the value: `off` would mean the thing is on."""
    offenders = [name for name in _boolean_fields() if "_DISABLED" in name]
    assert offenders == []


def test_every_old_shape_is_still_an_alias_of_its_new_name():
    """A rename that drops the old name breaks an environment file silently."""
    for klass in type(Config).__mro__:
        for name, value in vars(klass).items():
            if not isinstance(value, EnvField):
                continue
            for old in value.deprecated_aliases:
                assert old != name, f"{name} lists itself as deprecated"
