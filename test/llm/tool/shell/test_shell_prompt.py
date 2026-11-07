"""What the Shell schema says, rather than what it runs.

These are prompt tests: they pin the text pydantic-ai puts in front of the
model — the tool-level docstring, and each parameter's own description in the
JSON schema. A sentence here is the whole point, so a behavior test that a
command actually runs belongs in `test_shell_command.py` instead. Split out of
that file when it crossed the 500-line test ratchet
(`test/architecture/test_test_file_size_ratchet.py`).
"""

from zrb.llm.tool.shell import run_shell_command


def test_timeout_docstring_states_seconds_not_milliseconds():
    """The unit must be explicit in the description the model reads.

    Every other agent-shell tool in wide use takes milliseconds (default
    120000), so a bare `timeout: int = 120` invites millisecond values. One
    benchmarked model passed 15000 meaning 15s, got 15000 seconds, and its
    otherwise-perfect run was recorded as a timeout.

    Checked against the `timeout` parameter's own schema description (not the
    tool-level docstring) — that is the text pydantic-ai actually surfaces
    next to the field the model is filling in; see ADR-0055's amendment on
    per-parameter schema binding.
    """
    from pydantic_ai import Tool

    desc = Tool(run_shell_command).function_schema.json_schema["properties"]["timeout"][
        "description"
    ]

    assert "SECONDS" in desc
    assert "not milliseconds" in desc


def test_timeout_docstring_points_long_running_work_at_background():
    """Large timeouts should point callers to background execution."""
    from pydantic_ai import Tool

    desc = Tool(run_shell_command).function_schema.json_schema["properties"][
        "background"
    ]["description"]

    assert "long-running" in desc
    assert "server" in desc


def test_docstring_points_unbounded_output_at_a_summarizing_form():
    """Unbounded output should point callers to bounded commands."""
    doc = run_shell_command.__doc__ or ""

    assert "--stat" in doc
    assert "timeout" in doc


def test_docstring_puts_a_known_sequence_in_one_call():
    """Steps already known to run in order cost a round each unless chained.

    Every round re-sends the whole conversation, so `&&` is what makes the
    second command cheap. The operator differs per shell, and a runtime shell
    has none — the docstring has to name each, and it has to show one.
    """
    doc = " ".join((run_shell_command.__doc__ or "").split())

    assert "&&" in doc
    assert "PowerShell" in doc
    assert "node/ruby/php" in doc
    assert "git fetch && git rebase origin/main" in doc


def test_shell_asks_for_a_spoken_purpose():
    """The schema offers `purpose`, and its description says it is spoken."""
    from pydantic_ai import Tool

    desc = Tool(run_shell_command).function_schema.json_schema["properties"]["purpose"][
        "description"
    ]

    assert "read aloud" in desc


def test_docstring_tells_the_model_to_fill_the_purpose():
    doc = run_shell_command.__doc__ or ""

    assert "purpose" in doc
