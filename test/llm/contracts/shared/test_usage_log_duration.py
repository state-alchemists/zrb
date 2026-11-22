"""A line's duration, measured where the run happened.

`record_agent_usage` takes the number instead of reading a clock: a writer cannot
time a run it did not make. Each standalone call site starts a monotonic clock
before its model call and hands the elapsed milliseconds over, so `/usage`'s wall
time covers the hooks, the judge and the namer rather than only the turn loop.
"""

import time

from zrb.llm.contracts.shared.usage_log import get_elapsed_ms


def test_a_duration_is_measured_off_a_monotonic_clock():
    """Monotonic, so a clock correction mid-run cannot make a duration negative."""
    assert get_elapsed_ms(time.monotonic() - 0.25) >= 250
    assert get_elapsed_ms(time.monotonic()) == 0
