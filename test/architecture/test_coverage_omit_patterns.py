"""Coverage omit patterns must be cwd-independent.

A relative `src/zrb/__main__.py` matched nothing in subprocess coverage and
returned the file to the report at 74%; `**/`-prefixed patterns remain stable.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
COVERAGERC = REPO_ROOT / ".coveragerc"
OMIT_HEADING = "omit ="


def _omit_patterns() -> list[str]:
    """Return active `[run] omit` entries."""
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
            break
        patterns.append(stripped)
    return patterns


def test_the_omit_list_is_actually_parsed():
    """Fail if parsing stops finding omit entries."""
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
