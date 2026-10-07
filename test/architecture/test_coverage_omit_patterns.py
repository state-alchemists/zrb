"""Coverage omit patterns must be cwd-independent.

`./zrb-test.sh` runs the suite under xdist, and `pytest-cov.pth` starts coverage
again inside every subprocess a test spawns — `test/test_main_process.py` runs
`python -m zrb` from a scratch directory. Coverage resolves a *relative* omit
pattern against the cwd of whichever process reads the config, so the
repo-relative `src/zrb/__main__.py` this list used to carry matched nothing in
those subprocesses: the file was measured, and it reappeared in the report at
74% while the `**/__init__.py` entry beside it omitted every package init
cleanly. The `**/`-prefixed form matches on the basename (or on any directory),
so it holds wherever the process runs.

This is worth pinning because the failure is silent. A relative pattern raises
nothing and fails no gate — it only puts a file back into the report under its
own coverage, which is invisible unless you already know it should be absent.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
COVERAGERC = REPO_ROOT / ".coveragerc"
OMIT_HEADING = "omit ="


def _omit_patterns() -> list[str]:
    """Every active entry of the `[run] omit` list, comments and blanks dropped."""
    patterns: list[str] = []
    collecting = False
    for line in COVERAGERC.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not collecting:
            collecting = stripped == OMIT_HEADING
            continue
        if not stripped or stripped.startswith("#"):
            continue
        if not line[:1].isspace():
            break  # a new section or option ends the list
        patterns.append(stripped)
    return patterns


def test_the_omit_list_is_actually_parsed():
    """A parser that stopped matching would leave the check below guarding nothing."""
    assert _omit_patterns(), (
        f"no entries parsed from {COVERAGERC.name}'s `[run] omit` list — the "
        "parsing above has drifted from the file, so the invariant below holds "
        "vacuously"
    )


def test_every_omit_pattern_is_cwd_independent():
    relative = [p for p in _omit_patterns() if not p.startswith(("**/", "/"))]
    assert not relative, (
        "Coverage resolves these omit pattern(s) against the cwd of the process "
        "that reads the config, and the suite measures subprocesses whose cwd is "
        "a scratch directory — so a repo-relative entry omits nothing there and "
        "the file quietly returns to the report. Prefix each with `**/`:\n"
        + "\n".join(f"  {p}" for p in relative)
    )
