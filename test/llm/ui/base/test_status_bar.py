"""Tests for BaseUIStatusBar (the working timer, running tools and badges)."""

from unittest.mock import patch

from zrb.llm.ui.base.status_bar import BaseUIStatusBar, RunningTool


def test_the_working_timer_covers_the_current_period_only():
    bar = BaseUIStatusBar()
    assert bar.working_started_at is None

    with patch("zrb.llm.ui.base.status_bar.time.monotonic", return_value=100.0):
        bar.start_working()
    assert bar.working_started_at == 100.0

    with patch("zrb.llm.ui.base.status_bar.time.monotonic", return_value=200.0):
        bar.start_working()
    assert bar.working_started_at == 100.0

    bar.stop_working()
    assert bar.working_started_at is None


def test_a_period_after_a_stop_takes_the_new_start():
    bar = BaseUIStatusBar()
    with patch("zrb.llm.ui.base.status_bar.time.monotonic", return_value=1.0):
        bar.start_working()
    bar.stop_working()

    with patch("zrb.llm.ui.base.status_bar.time.monotonic", return_value=2.0):
        bar.start_working()

    assert bar.working_started_at == 2.0


def test_no_running_tool_before_one_starts():
    assert BaseUIStatusBar().running_tool is None


def test_a_started_tool_call_records_its_name_id_and_start_time():
    bar = BaseUIStatusBar()

    with patch("zrb.llm.ui.base.status_bar.time.monotonic", return_value=999.0):
        bar.start_tool_call("Shell", "call_1")

    assert bar.running_tool == RunningTool("Shell", "call_1", 999.0)


def test_the_running_tool_is_the_most_recently_started_call():
    bar = BaseUIStatusBar()
    with patch("zrb.llm.ui.base.status_bar.time.monotonic", return_value=10.0):
        bar.start_tool_call("Shell", "call_1")
    with patch("zrb.llm.ui.base.status_bar.time.monotonic", return_value=20.0):
        bar.start_tool_call("WebSearch", "call_2")

    assert bar.running_tool == RunningTool("WebSearch", "call_2", 20.0)

    bar.end_tool_call("call_2")

    assert bar.running_tool == RunningTool("Shell", "call_1", 10.0)


def test_a_finished_call_clears_only_its_own_timer():
    bar = BaseUIStatusBar()
    with patch("zrb.llm.ui.base.status_bar.time.monotonic", return_value=10.0):
        bar.start_tool_call("Shell", "call_1")
    with patch("zrb.llm.ui.base.status_bar.time.monotonic", return_value=20.0):
        bar.start_tool_call("WebSearch", "call_2")

    bar.end_tool_call("call_2")

    assert bar.running_tool == RunningTool("Shell", "call_1", 10.0)


def test_an_unknown_call_id_leaves_the_running_tool_alone():
    bar = BaseUIStatusBar()
    with patch("zrb.llm.ui.base.status_bar.time.monotonic", return_value=10.0):
        bar.start_tool_call("Shell", "call_1")

    bar.end_tool_call("call_9")

    assert bar.running_tool == RunningTool("Shell", "call_1", 10.0)


def test_ending_a_call_with_no_id_clears_every_running_tool():
    bar = BaseUIStatusBar()
    bar.start_tool_call("Shell", "call_1")
    bar.start_tool_call("WebSearch", "call_2")

    bar.end_tool_call()

    assert bar.running_tool is None


def test_badges_are_set_replaced_and_removed_by_key():
    bar = BaseUIStatusBar()
    assert bar.badges == ()

    bar.set_badge("mic", "🎤 listening")
    bar.set_badge("camera", "📷 on")
    assert bar.badges == ("🎤 listening", "📷 on")

    bar.set_badge("mic", "🎙️ hearing you…")
    assert bar.badges == ("🎙️ hearing you…", "📷 on")

    bar.set_badge("mic", None)
    bar.set_badge("gone", None)
    assert bar.badges == ("📷 on",)
