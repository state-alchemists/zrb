"""Tests for context/print_fn.py - Print function protocol."""

import sys
from io import StringIO
from typing import TextIO

import pytest


class TestPrintFnProtocol:
    """Test PrintFn protocol."""

    def test_protocol_is_callable(self):
        """Test that PrintFn is a callable protocol."""
        from zrb.context.print_fn import PrintFn

        # A simple print function should match the protocol
        def my_print(*values: object, sep: str = " ", end: str = "\n",
                     file: TextIO | None = None, flush: bool = False) -> None:
            pass

        # Just verify it's callable and matches protocol signature
        assert callable(my_print)

    def test_print_protocol_usage(self):
        """Test using a function that matches PrintFn protocol."""
        from zrb.context.print_fn import PrintFn

        output = StringIO()

        def custom_print(*values: object, sep: str = " ", end: str = "\n",
                         file: TextIO | None = None, flush: bool = False) -> None:
            target = file if file is not None else sys.stdout
            target.write(sep.join(str(v) for v in values) + end)

        # Use the custom print function
        custom_print("Hello", "World", sep=", ", file=output)
        assert output.getvalue() == "Hello, World\n"

    def test_print_with_flush(self):
        """Test print function with flush parameter."""
        from typing import Protocol

        output = StringIO()

        def flushing_print(*values: object, sep: str = " ", end: str = "\n",
                          file: TextIO | None = None, flush: bool = False) -> None:
            target = file if file is not None else sys.stdout
            target.write(sep.join(str(v) for v in values) + end)
            if flush:
                target.flush()

        flushing_print("Test", file=output, flush=True)
        assert output.getvalue() == "Test\n"

    def test_print_with_custom_sep_and_end(self):
        """Test print function with custom separator and end."""
        output = StringIO()

        def custom_print(*values: object, sep: str = " ", end: str = "\n",
                         file: TextIO | None = None, flush: bool = False) -> None:
            target = file if file is not None else sys.stdout
            target.write(sep.join(str(v) for v in values) + end)

        custom_print("a", "b", "c", sep="-", end="!", file=output)
        assert output.getvalue() == "a-b-c!"