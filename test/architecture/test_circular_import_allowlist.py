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

An audit found 17 comments giving a circular-import justification in
non-canonical wording, invisible to the regex below (empirically confirmed —
by hoisting each import to module level in a scratch copy and observing the
resulting `ImportError` — rather than taken on the comment's word). Of those
17, 12 were mislabeled (8 plain "transitively heavy" imports with no real
cycle, 4 test-patch-seam imports already justified elsewhere) and reworded to
their real category. The other 6 (a 6th, in `hook/creator.py`, surfaced
separately during a later change) were genuine — and all 6 have since been
eliminated, not just deferred:

- `hook/creator.py`'s `create_agent` import cycled because two eager
  importers within `zrb.llm.agent`'s import closure (`hook/manager.py`,
  `agent/hook_agent.py`) each imported its functions at module level.
  Deferring those two importers' own imports (not `hook/creator.py`'s)
  removed it from the closure entirely.
- The other 5 (in `agent/run/setup.py` and `live_context.py`) all traced back
  to the same root cause: two genuinely dependency-free "leaf" modules —
  ambient `ContextVar` state and `ToolReturn` construction — lived *inside*
  the `zrb.llm.agent` package (`agent/run/runtime_state.py`,
  `agent/tool_result.py`) purely by original placement, with no actual need
  for anything else in that package. Importing either from outside forced
  Python to run `zrb.llm.agent`'s package `__init__` first (parent packages
  load before submodules), which is what made `zrb.llm.ui`, `zrb.llm.tool`,
  and `live_context.py` circular with `zrb.llm.agent` whenever they needed
  either one. Moving both out to top-level `zrb.llm.agent_state` and
  `zrb.llm.agent_tool_result` — genuinely dependency-free locations, not
  nested under anything `zrb.llm.agent`'s own `__init__` reaches — removed
  the edge at its source. Confirmed by re-running the same hoist-and-import
  check after the move: every one of the 5 imports that used to raise
  `ImportError` now succeeds, so they were hoisted to real module-level
  imports too (the "lazy" tag on them is gone entirely, not recategorized).

This is why the allowlist below is empty rather than a lingering "these 6 are
just how it is" list. A useful diagnostic for finding more of this shape:
`zrb.llm.agent` and `zrb.llm.ui`'s eager-import closures are each ~400 of
this repo's ~430 zrb modules (computed by walking every module-level import
transitively, excluding `if TYPE_CHECKING:` blocks) — a module reachable
from many places, like the two moved here, is invisible to a fix that only
defers the one import site you happened to find, since the others keep it
reachable regardless.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
SRC = REPO_ROOT / "src" / "zrb"

# Path relative to src/zrb -> number of "# lazy: circular" occurrences
# expected in that file. Add an entry in the same diff that introduces a
# genuine circular-import workaround, with a reason in the comment itself.
CIRCULAR_IMPORT_ALLOWLIST: dict[str, int] = {}


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
