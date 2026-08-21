from zrb.util.todo.duration import add_duration, format_duration, parse_duration


def test_duration_parsing():
    assert parse_duration("1h") == 3600
    assert parse_duration("1m") == 60
    assert parse_duration("1h30m") == 5400
    assert parse_duration("1d") == 86400


def test_add_duration():
    assert add_duration("1h", "30m") == "1h30m"
    assert add_duration("50m", "20m") == "1h10m"


class TestDurationFunctions:
    """Tests for duration parsing edge cases."""

    def test_parse_duration_complex(self):
        assert parse_duration("1w2d3h4m5s") == 604800 + 172800 + 10800 + 240 + 5

    def test_parse_duration_zero(self):
        assert parse_duration("") == 0

    def test_parse_duration_months(self):
        # M = months (2592000 seconds each)
        assert parse_duration("1M") == 2592000

    def test_format_duration_zero(self):
        assert format_duration(0) == "0s"
