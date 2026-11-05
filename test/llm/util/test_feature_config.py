import logging
from dataclasses import dataclass

import pytest

from zrb.config.config import CFG
from zrb.contextvars import current_chat_session_id
from zrb.llm.camera.config import CameraConfig
from zrb.llm.dictation.config import DictationConfig
from zrb.llm.screenshot.config import ScreenshotConfig
from zrb.llm.speech.config import SpeechConfig
from zrb.llm.util import feature_config
from zrb.llm.util.feature_config import (
    FeatureSessions,
    accepts_renamed_fields,
    close_feature_sessions,
    current_session_key,
    get_session_ui,
    replace_feature_sessions,
    replace_registration,
    reset_session_ui,
    resolve_from_cfg,
    set_session_ui,
)


@dataclass
class _Config:
    commands: list[str] | None = None
    device: str | None = None


def test_none_fields_are_read_from_cfg_at_resolve_time(monkeypatch):
    config = _Config(device="/dev/video2")
    monkeypatch.setattr(CFG, "LLM_CAMERA_COMMANDS", ["/snap"])

    resolved = resolve_from_cfg(config, "LLM_CAMERA_")

    assert resolved == _Config(commands=["/snap"], device="/dev/video2")
    assert config.commands is None


def test_resolved_lists_are_copies(monkeypatch):
    shared = ["/snap"]
    monkeypatch.setattr(CFG, "LLM_CAMERA_COMMANDS", shared)

    resolve_from_cfg(_Config(), "LLM_CAMERA_").commands.append("/extra")

    assert shared == ["/snap"]


class _Task:
    def __init__(self, with_remove: bool = True):
        self.commands: list = []
        if with_remove:
            self.remove_custom_command = self.commands.remove

    def append_custom_command(self, command):
        self.commands.append(command)


def test_registering_a_feature_again_replaces_it():
    task = _Task()

    replace_registration(task, "camera", [("append_custom_command", "first")])
    replace_registration(task, "speech", [("append_custom_command", "other")])
    replace_registration(task, "camera", [("append_custom_command", "second")])

    assert task.commands == ["other", "second"]


def test_a_task_that_cannot_remove_keeps_the_earlier_item():
    task = _Task(with_remove=False)

    replace_registration(task, "speech", [("append_custom_command", "first")])
    replace_registration(task, "speech", [("append_custom_command", "second")])

    assert task.commands == ["first", "second"]


def test_a_session_running_when_the_feature_is_replaced_is_closed_by_its_own_close():
    """A second `enable_*` call closes what the first left running, and the
    close callback that arrives with the new config is not necessarily the one
    that fits the session on its way out — so the old one has to close it."""
    task = _Task()
    closed_by = []

    first = replace_feature_sessions(
        task,
        "speech",
        lambda: "old",
        lambda session: closed_by.append(("old", session)),
    )
    first.get()
    replace_feature_sessions(
        task,
        "speech",
        lambda: "new",
        lambda session: closed_by.append(("new", session)),
    )

    assert closed_by == [("old", "old")]


def test_a_feature_replaced_again_builds_from_the_new_factory():
    task = _Task()
    sessions = replace_feature_sessions(
        task, "speech", lambda: "first", lambda _s: None
    )
    assert sessions.get() == "first"

    replace_feature_sessions(task, "speech", lambda: "second", lambda _s: None)

    assert sessions.get() == "second"


def test_each_session_has_its_own_ui_until_it_ends():
    first, second = object(), object()
    token = current_chat_session_id.set("first")
    try:
        set_session_ui(first)  # type: ignore[arg-type]
        first_key = current_session_key()
        current_chat_session_id.set("second")
        set_session_ui(second)  # type: ignore[arg-type]
        assert get_session_ui() is second
        reset_session_ui()
        assert get_session_ui() is None

        current_chat_session_id.set("first")
        assert get_session_ui() is first
        close_feature_sessions(first_key)
        assert get_session_ui() is None
    finally:
        current_chat_session_id.reset(token)


def test_one_feature_failing_to_close_does_not_keep_the_others_open(caplog):
    closed = []

    def broken_close(value):
        raise AttributeError("'object' object has no attribute 'set_status_badge'")

    broken = FeatureSessions(lambda: "broken", broken_close)
    working = FeatureSessions(lambda: "working", closed.append)
    token = current_chat_session_id.set("closing")
    try:
        broken.get()
        working.get()
        set_session_ui(object())  # type: ignore[arg-type]
        key = current_session_key()

        close_feature_sessions(key)

        assert closed == ["working"]
        assert get_session_ui() is None
        assert "set_status_badge" in caplog.text
    finally:
        current_chat_session_id.reset(token)


@accepts_renamed_fields(enable_tool="tool_enabled")
@dataclass
class _Renamed:
    tool_enabled: bool | None = None


@pytest.fixture(autouse=True)
def fresh_rename_warnings(monkeypatch):
    """Each test starts with no warning spent, so "warns once" is measurable."""
    monkeypatch.setattr(feature_config, "_renamed_field_warnings", set())


def test_an_old_keyword_sets_the_field_that_replaced_it(caplog):
    caplog.set_level(logging.WARNING)

    config = _Renamed(enable_tool=True)

    assert config.tool_enabled is True
    assert [
        record.getMessage()
        for record in caplog.records
        if "enable_tool" in record.getMessage()
    ] == ["_Renamed(enable_tool=...) is deprecated; use tool_enabled instead."]


def test_the_current_keyword_wins_when_both_are_given():
    config = _Renamed(enable_tool=False, tool_enabled=True)

    assert config.tool_enabled is True


def test_the_old_attribute_reads_and_writes_the_new_field(caplog):
    caplog.set_level(logging.WARNING)
    config = _Renamed(tool_enabled=True)

    assert config.enable_tool is True
    config.enable_tool = False

    assert config.tool_enabled is False


def test_the_warning_is_said_once(caplog):
    caplog.set_level(logging.WARNING)

    for _ in range(3):
        _Renamed(enable_tool=True)
        _Renamed().enable_tool

    assert len([r for r in caplog.records if "enable_tool" in r.getMessage()]) == 1


def test_a_new_keyword_says_nothing(caplog):
    caplog.set_level(logging.WARNING)

    _Renamed(tool_enabled=True)

    assert [r for r in caplog.records if r.levelno == logging.WARNING] == []


@pytest.mark.parametrize(
    "build, field_name, expected",
    [
        (lambda: CameraConfig(enable_tool=True), "tool_enabled", True),
        (lambda: ScreenshotConfig(enable_tool=True), "tool_enabled", True),
        (
            lambda: DictationConfig(enable_echo_cancel=True),
            "echo_cancel_enabled",
            True,
        ),
        (lambda: DictationConfig(detect_emotion=True), "detect_emotion_enabled", True),
        (
            lambda: DictationConfig(emotion_out_of_process=True),
            "emotion_out_of_process_enabled",
            True,
        ),
        (
            lambda: SpeechConfig(missing_block_notice_enabled=False),
            "block_notice_enabled",
            False,
        ),
    ],
    ids=[
        "camera",
        "screenshot",
        "dictation-echo",
        "dictation-emotion",
        "dictation-subprocess",
        "speech",
    ],
)
def test_a_feature_config_still_takes_the_field_names_it_had(
    build, field_name, expected
):
    """Renaming a public constructor argument would crash a plugin at import."""
    assert getattr(build(), field_name) is expected
