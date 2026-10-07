"""The counts AGENTS.md quotes are measured, not remembered.

`AGENTS.md`'s verb rule states how many functions the tree holds, how many
distinct leading tokens they answer to, and what share of those tokens appears
once. Those numbers go stale silently: a rename or a new helper moves them
without touching the sentence, and the file was already wrong — it claimed
"5,000 functions … 596 distinct leading tokens, 43% of them used once" while the
tree measured 4,466 / 488 / 39.5%. A guide whose argument is "verify against
data" should not carry a number nobody re-measures, so `scripts/doc_counts.py`
computes the three and this holds the sentence to them.

The fix when this fails is one command:

    python scripts/doc_counts.py --write
"""

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "doc_counts", REPO_ROOT / "scripts" / "doc_counts.py"
)
assert _SPEC is not None and _SPEC.loader is not None
doc_counts = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = doc_counts
_SPEC.loader.exec_module(doc_counts)


def test_the_counts_sentence_is_still_found():
    """A reworded sentence would leave every check below guarding nothing.

    The numbers only mean something while the test can find the sentence that
    carries them, so losing it has to fail here rather than quietly pass.
    """
    assert doc_counts.documented() is not None, (
        f"{doc_counts.AGENTS.name} no longer contains the counts sentence this "
        "test reads (the `N functions, which currently answer to M distinct "
        "leading tokens, P% of them used once` clause). Restore the wording, or "
        "update `scripts/doc_counts.py`'s `_SENTENCE` together with it."
    )


def test_the_documented_counts_match_the_tree():
    measured = doc_counts.measure()
    stated = doc_counts.documented()
    assert stated == measured, (
        f"The counts in {doc_counts.AGENTS.name} no longer match the tree. "
        f"documented={stated} measured={measured}. Restate them with "
        "`python scripts/doc_counts.py --write`."
    )


def test_the_rewrite_restates_the_sentence_from_the_measurement():
    """The one command the failure above names has to actually fix it."""
    measured = doc_counts.measure()
    rewritten = doc_counts.rewrite(doc_counts.AGENTS.read_text(encoding="utf-8"), measured)
    assert doc_counts.documented(rewritten) == measured
