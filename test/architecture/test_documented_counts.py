"""Keep AGENTS.md's measured function counts synchronized.

The prior sentence claimed 5,000 / 596 / 43%, while the tree measured
4,466 / 488 / 39.5%; `scripts/doc_counts.py --write` is the fix.
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
    """Fail if the counts sentence disappears or is reworded."""
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
    """The named rewrite command must actually fix the sentence."""
    measured = doc_counts.measure()
    rewritten = doc_counts.rewrite(
        doc_counts.AGENTS.read_text(encoding="utf-8"), measured
    )
    assert doc_counts.documented(rewritten) == measured


def test_write_restates_the_sentence_in_place(tmp_path, monkeypatch):
    """The write path must restate the measured counts."""
    target = tmp_path / "AGENTS.md"
    target.write_text(
        "It answers to 5,000 functions, which currently answer to 596 distinct "
        "leading tokens, 43% of them used once.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(doc_counts, "AGENTS", target)
    assert doc_counts.main(["--write"]) == 0
    assert (
        doc_counts.documented(target.read_text(encoding="utf-8"))
        == doc_counts.measure()
    )


def test_write_refuses_to_claim_success_with_nothing_to_restate(tmp_path, monkeypatch):
    """`--write` must fail loudly when no counts sentence can be restated."""
    target = tmp_path / "AGENTS.md"
    untouched = "# No counts sentence lives here.\n"
    target.write_text(untouched, encoding="utf-8")
    monkeypatch.setattr(doc_counts, "AGENTS", target)
    assert doc_counts.main(["--write"]) == 1
    assert target.read_text(encoding="utf-8") == untouched
