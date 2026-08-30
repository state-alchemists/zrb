"""Guards against a `# lazy: circular` workaround creeping back in unreviewed.

Every one of these previously in the tree turned out, on inspection, to be
one of: a stale comment (the cycle it described no longer existed — code had
moved on), a mislabeled heavy-dependency or test-patch-seam deferral (a real
reason, just not this one), or a real cycle caused by a package `__init__.py`
eagerly re-exporting names nothing outside the package actually imported
(fixed by trimming the re-export, not by deferring the import). None were an
irreducible design constraint. See `zrb.llm.tool/__init__.py`'s and
`zrb.llm.prompt/__init__.py`'s docstrings for the two real cases of the last
pattern.

This doesn't ban a new one — a genuine cycle can still happen — it just
requires it to be declared here, in the same diff, with a reason, instead of
landing silently. Bumping `CIRCULAR_IMPORT_ALLOWLIST` off zero should be rare
enough that it always gets a second look.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
SRC = REPO_ROOT / "src" / "zrb"

# Path relative to src/zrb -> number of "# lazy: circular" occurrences
# expected in that file. Add an entry in the same diff that introduces a
# genuine circular-import workaround, with a reason in the comment itself.
#
# These 5 were found (and empirically confirmed as real cycles, by hoisting
# each import to module level in a scratch copy and observing the resulting
# ImportError) while auditing 17 comments that gave a circular-import
# justification in non-canonical wording, invisible to the regex below. The
# other 12 were mislabeled — 8 were plain "transitively heavy" imports with
# no real cycle, and 4 (in tool/web.py) were test-patch-seam imports already
# justified by a comment one block above; all 12 were recategorized rather
# than tagged circular, per this file's own docstring above.
CIRCULAR_IMPORT_ALLOWLIST: dict[str, int] = {
    "llm/agent/run/setup.py": 1,
    "llm/prompt/live_context.py": 4,
    "llm/hook/creator.py": 1,
}


def _circular_import_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in SRC.rglob("*.py"):
        n = len(re.findall(r"# lazy: circular", path.read_text()))
        if n:
            counts[str(path.relative_to(SRC))] = n
    return counts


def test_circular_import_workarounds_match_the_allowlist():
    actual = _circular_import_counts()
    assert actual == CIRCULAR_IMPORT_ALLOWLIST, (
        "`# lazy: circular` workarounds drifted from the allowlist — a file "
        "missing here, an extra file, or a changed count means a cycle was "
        "added, fixed, or moved. Update CIRCULAR_IMPORT_ALLOWLIST in this "
        f"file to match, in the same diff, with a reason.\nactual={actual}\n"
        f"expected={CIRCULAR_IMPORT_ALLOWLIST}"
    )
