"""Enforces the test-file split rule (AGENTS.md → Test Guidelines: split files
over 500 lines by feature group).

The rule was documented and unenforced, so 46 files had crossed it —
`llm/agent/run/test_runner.py` at 2049 lines, four times over. All 46 are now
split by feature group, so this holds at zero offenders with no allowlist: the
budget is the rule itself.

Splitting is by *feature*, not by size — `test_runner.py` became
`test_runner_history.py`, `_lifecycle`, `_deferred`, `_retry`, `_hooks`,
`_stop_hooks` and `_limits`. When a file legitimately outgrows the limit
again, split it the same way rather than adding an exemption here.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
TEST_ROOT = REPO_ROOT / "test"

MAX_TEST_FILE_LINES = 500


def test_no_test_file_exceeds_the_split_threshold():
    offenders = {
        str(path.relative_to(TEST_ROOT)): len(path.read_text().splitlines())
        for path in TEST_ROOT.rglob("test_*.py")
    }
    over = {name: n for name, n in offenders.items() if n > MAX_TEST_FILE_LINES}
    assert not over, (
        f"test file(s) over {MAX_TEST_FILE_LINES} lines: {over}. Split by "
        "feature group (AGENTS.md → Test Guidelines)."
    )
