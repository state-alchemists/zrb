"""`zrb chat`'s launch flags: one run's answer over the deployment's.

The rule under test is `--sandbox`'s: an empty flag says nothing, a value holds
for this process, and a value the setting would refuse is refused here too.
"""

import os

import pytest

from zrb.builtin.llm.chat_flags import apply_launch_flags
from zrb.config.config import CFG
from zrb.context.context import Context
from zrb.context.shared_context import SharedContext

# flag, setting, a value, what the setting reads back.
SETTINGS = (
    ("voice", "LLM_VOICE", "conversation", "conversation"),
    ("volume", "LLM_SPEECH_VOLUME", "40", 40),
    ("thinking", "LLM_THINKING", "medium", "medium"),
    ("profile", "LLM_PROFILE", "minimal", "minimal"),
    ("memory", "LLM_MEMORY_ENABLED", "false", False),
    ("self-review", "LLM_SELF_REVIEW_ENABLED", "true", True),
)

FLAGS = tuple(flag for flag, _, _, _ in SETTINGS) + ("judge",)

JUDGE_HALVES = ("LLM_SHELL_JUDGE_ENABLED", "LLM_SHELL_JUDGE_AUTO_APPROVE_ENABLED")


@pytest.fixture
def kept_settings():
    """Put every setting back where it was.

    `CFG` writes the process environment rather than a field, so a test that
    overrides a launch flag would otherwise decide what the next test reads.
    """
    names = [name for _, name, _, _ in SETTINGS] + list(JUDGE_HALVES)
    keys: dict[str, str] = {}
    for name in names:
        field = CFG.get_settable_field(name)
        assert field is not None, f"{name} is not a settable setting"
        keys[name] = field.env_key(CFG.ENV_PREFIX)
    before = {name: os.environ.get(key) for name, key in keys.items()}
    yield
    for name, key in keys.items():
        raw = before[name]
        if raw is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = raw


def _ctx(**inputs: str) -> Context:
    return Context(SharedContext(input=dict(inputs)), "test", 0, "")


@pytest.mark.parametrize("flag, name, raw, expected", SETTINGS)
def test_a_flag_overrides_its_setting(flag, name, raw, expected, kept_settings):
    apply_launch_flags(_ctx(**{flag: raw}))
    assert getattr(CFG, name) == expected


def test_an_empty_flag_leaves_the_deployment_alone(kept_settings):
    CFG.LLM_VOICE = "turns"
    apply_launch_flags(_ctx())
    assert CFG.LLM_VOICE == "turns"


def test_a_whitespace_flag_is_an_empty_one(kept_settings):
    CFG.LLM_VOICE = "turns"
    apply_launch_flags(_ctx(voice="   "))
    assert CFG.LLM_VOICE == "turns"


def test_auto_approve_turns_on_both_halves(kept_settings):
    """The second grant is meaningless without the first: a session cannot skip
    prompts it never consults the judge about."""
    CFG.LLM_SHELL_JUDGE_ENABLED = False
    CFG.LLM_SHELL_JUDGE_AUTO_APPROVE_ENABLED = False

    apply_launch_flags(_ctx(judge="auto-approve"))

    assert CFG.LLM_SHELL_JUDGE_ENABLED is True
    assert CFG.LLM_SHELL_JUDGE_AUTO_APPROVE_ENABLED is True


def test_judge_off_leaves_the_auto_half_where_the_deployment_put_it(kept_settings):
    """`--judge off` is the consultation switch; it says nothing about the half
    that removes the prompt, which matters only while consultation is on."""
    CFG.LLM_SHELL_JUDGE_ENABLED = True
    CFG.LLM_SHELL_JUDGE_AUTO_APPROVE_ENABLED = True

    apply_launch_flags(_ctx(judge="off"))

    assert CFG.LLM_SHELL_JUDGE_ENABLED is False
    assert CFG.LLM_SHELL_JUDGE_AUTO_APPROVE_ENABLED is True


def test_a_volume_outside_the_range_is_refused(kept_settings):
    """Clamping happens at playback, so a mistyped flag would otherwise be read
    as a request for full volume and nothing would say so."""
    with pytest.raises(ValueError, match="0-200"):
        apply_launch_flags(_ctx(volume="400"))


def test_a_volume_that_is_not_a_number_is_refused(kept_settings):
    """The range check narrows the setting's cast, so it also refuses a value
    that never reached it as a number."""
    from zrb.builtin.llm.chat_flags import _checked_volume

    with pytest.raises(ValueError, match="0-200"):
        _checked_volume("40")


def test_an_unknown_profile_is_refused(kept_settings):
    """`resolve_profile` falls back to `standard` on a name it does not know, so
    a typo would otherwise look like it worked."""
    with pytest.raises(ValueError, match="minimal, standard, capable, auto"):
        apply_launch_flags(_ctx(profile="clever"))


def test_a_value_the_setting_cannot_cast_is_refused(kept_settings):
    with pytest.raises(ValueError):
        apply_launch_flags(_ctx(memory="maybe"))


def test_the_builtin_task_declares_every_launch_flag(kept_settings):
    """A flag added to the map but not to the task is a setting nothing can reach."""
    from zrb.builtin.llm.chat import llm_chat

    declared = {task_input.name for task_input in llm_chat.own_inputs}
    assert set(FLAGS) <= declared
