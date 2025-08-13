import datetime

import pytest

from zrb.util.cron import handle_special_cron_patterns, match_cron, parse_cron_field


def test_parse_cron_field_wildcard():
    assert parse_cron_field("*", 0, 59) == set(range(60))
    assert parse_cron_field("*", 1, 12) == set(range(1, 13))


def test_parse_cron_field_step():
    assert parse_cron_field("*/10", 0, 59) == {0, 10, 20, 30, 40, 50}
    assert parse_cron_field("*/5", 1, 31) == {1, 6, 11, 16, 21, 26, 31}


def test_parse_cron_field_range():
    assert parse_cron_field("1-5", 0, 59) == {1, 2, 3, 4, 5}
    assert parse_cron_field("10-12", 0, 23) == {10, 11, 12}


def test_parse_cron_field_list():
    assert parse_cron_field("1,3,5", 0, 59) == {1, 3, 5}
    assert parse_cron_field("10,20,30", 0, 59) == {10, 20, 30}


def test_parse_cron_field_range_with_step():
    assert parse_cron_field("1-10/2", 0, 59) == {1, 3, 5, 7, 9}
    assert parse_cron_field("10-20/3", 0, 59) == {10, 13, 16, 19}


def test_parse_cron_field_individual_value():
    assert parse_cron_field("5", 0, 59) == {5}
    assert parse_cron_field("12", 0, 23) == {12}


def test_handle_special_cron_patterns_yearly():
    dt = datetime.datetime(2024, 1, 1, 0, 0)
    assert handle_special_cron_patterns("@yearly", dt) is True
    dt = datetime.datetime(2024, 1, 1, 0, 1)
    assert handle_special_cron_patterns("@yearly", dt) is False
    dt = datetime.datetime(2024, 1, 2, 0, 0)
    assert handle_special_cron_patterns("@yearly", dt) is False


def test_handle_special_cron_patterns_monthly():
    dt = datetime.datetime(2024, 5, 1, 0, 0)
    assert handle_special_cron_patterns("@monthly", dt) is True
    dt = datetime.datetime(2024, 5, 1, 0, 1)
    assert handle_special_cron_patterns("@monthly", dt) is False
    dt = datetime.datetime(2024, 5, 2, 0, 0)
    assert handle_special_cron_patterns("@monthly", dt) is False


def test_handle_special_cron_patterns_weekly():
    dt = datetime.datetime(2024, 4, 29, 0, 0)  # Monday
    assert handle_special_cron_patterns("@weekly", dt) is True
    dt = datetime.datetime(2024, 4, 30, 0, 0)  # Tuesday
    assert handle_special_cron_patterns("@weekly", dt) is False
    dt = datetime.datetime(2024, 4, 29, 0, 1)
    assert handle_special_cron_patterns("@weekly", dt) is False


def test_handle_special_cron_patterns_daily():
    dt = datetime.datetime(2024, 5, 10, 0, 0)
    assert handle_special_cron_patterns("@daily", dt) is True
    dt = datetime.datetime(2024, 5, 10, 0, 1)
    assert handle_special_cron_patterns("@daily", dt) is False
    dt = datetime.datetime(2024, 5, 10, 1, 0)
    assert handle_special_cron_patterns("@daily", dt) is False


def test_handle_special_cron_patterns_hourly():
    dt = datetime.datetime(2024, 5, 10, 10, 0)
    assert handle_special_cron_patterns("@hourly", dt) is True
    dt = datetime.datetime(2024, 5, 10, 10, 1)
    assert handle_special_cron_patterns("@hourly", dt) is False


def test_handle_special_cron_patterns_minutely():
    dt = datetime.datetime(2024, 5, 10, 10, 30)
    assert handle_special_cron_patterns("@minutely", dt) is True


def test_handle_special_cron_patterns_unknown():
    dt = datetime.datetime(2024, 5, 10, 10, 30)
    assert handle_special_cron_patterns("@unknown", dt) is False


def test_match_cron_standard():
    dt = datetime.datetime(2024, 5, 10, 10, 30)  # Friday, May 10, 2024 at 10:30
    assert (
        match_cron("30 10 10 5 *", dt) is True
    )  # Specific minute, hour, day, month, any day of week
    assert (
        match_cron("30 10 * * 5", dt) is True
    )  # Specific minute, hour, any day of month, any month, specific day of week (Friday)
    assert match_cron("*/15 * * * *", dt) is True  # Every 15 minutes
    assert match_cron("0 0 * * *", dt) is False  # Midnight daily


def test_match_cron_special_yearly():
    dt = datetime.datetime(2025, 1, 1, 0, 0)
    assert match_cron("@yearly", dt) is True
    dt = datetime.datetime(2024, 1, 1, 0, 0)
    assert match_cron("@yearly", dt) is True
    dt = datetime.datetime(2025, 1, 1, 0, 1)
    assert match_cron("@yearly", dt) is False


def test_match_cron_special_monthly():
    dt = datetime.datetime(2025, 5, 1, 0, 0)
    assert match_cron("@monthly", dt) is True
    dt = datetime.datetime(2025, 5, 1, 0, 1)
    assert match_cron("@monthly", dt) is False


def test_match_cron_special_weekly():
    dt = datetime.datetime(2025, 4, 28, 0, 0)  # Monday, April 28, 2025
    assert match_cron("@weekly", dt) is True
    dt = datetime.datetime(2025, 4, 29, 0, 0)  # Tuesday, April 29, 2025
    assert match_cron("@weekly", dt) is False


def test_match_cron_special_daily():
    dt = datetime.datetime(2025, 5, 10, 0, 0)
    assert match_cron("@daily", dt) is True
    dt = datetime.datetime(2025, 5, 10, 0, 1)
    assert match_cron("@daily", dt) is False


def test_match_cron_special_hourly():
    dt = datetime.datetime(2025, 5, 10, 10, 0)
    assert match_cron("@hourly", dt) is True
    dt = datetime.datetime(2025, 5, 10, 10, 1)
    assert match_cron("@hourly", dt) is False


def test_match_cron_special_minutely():
    dt = datetime.datetime(2025, 5, 10, 10, 30)
    assert match_cron("@minutely", dt) is True


def test_match_cron_invalid_pattern():
    dt = datetime.datetime(2025, 5, 10, 10, 30)
    with pytest.raises(ValueError):
        match_cron("invalid cron pattern", dt)
