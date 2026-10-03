"""Tests for IntInput — the input most builtin tasks declare their numbers with.

`IntInput` had no mirrored test file: it was covered through its callers
(`test/runner/test_cli.py`, `test/runner/test_web.py`), which exercise the happy
path only. A value it has to *reject* is asserted nowhere in the suite, which is
why the raw `int()` message reached users for as long as it did.
"""

import pytest

from zrb.context.shared_context import SharedContext
from zrb.input.int_input import IntInput


def test_int_input_parse_str_value():
    int_input = IntInput(name="count")
    shared_ctx = SharedContext()
    int_input.update_shared_context(shared_ctx, str_value="42")
    assert shared_ctx.input.count == 42
    assert isinstance(shared_ctx.input.count, int)


def test_int_input_get_default_str():
    int_input = IntInput(name="count", default=7)
    assert int_input.get_default_str(SharedContext()) == "7"


def test_int_input_rejected_value_names_the_flag_and_the_accepted_shape():
    int_input = IntInput(name="ticket-count")
    with pytest.raises(ValueError) as excinfo:
        int_input.update_shared_context(SharedContext(), str_value="abc")
    message = str(excinfo.value)
    assert "'ticket-count'" in message
    assert "'abc'" in message
    assert "an integer" in message
    assert "invalid literal" not in message
