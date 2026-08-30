"""Guards against a `# lazy:` comment that doesn't justify itself.

AGENTS.md (Imports) requires every in-function import to carry a `# lazy:
<reason>` comment matching one of four categories: heavy third-party
deferral, transitively-heavy-via-internal, circular import, or a test-patch
seam. `test_circular_import_allowlist.py` only checks the circular category
(and only the canonical `# lazy: circular` tag). This test classifies every
`# lazy:` comment in the tree into one of those categories (folding
call-frequency/"hot path" avoidance of an internal import under the
transitively-heavy-via-internal category — it's the same "avoid this
import's cost" concern, just keyed to call frequency instead of raw weight)
and fails if any comment doesn't match at least one.

Before landing, every comment in the tree was read and reclassified rather
than pattern-matched blindly: an audit found 291 `# lazy:` comments, of
which 20 didn't fit any category as originally worded — 10 were a bare
`# lazy: defer CFG load` with no stated reason (reworded to name the real
one: CFG composes 15 mixins), 4 were hot-path rationale with no keyword this
test recognizes (reworded to say "hot path" explicitly), 4 were vague/no
reason (two were hoisted to module level entirely — they turned out to be
unjustified: `stat` is a free stdlib import, and `render_live_context_async`
was already sitting next to its module-level-imported sync twin), and 1 was
a stdlib-heavy deferral (urllib/zipfile) that category 1 as written doesn't
literally cover (reworded to "heavy (stdlib)"). See
`test_circular_import_allowlist.py`'s docstring for the separate, larger
finding this same audit made about mislabeled circular-import comments.

This doesn't ban new categories from emerging — it just means a `# lazy:`
comment this test can't classify is a signal to either reword it to state
its real reason, or (if it's a genuinely new kind of reason) update the
keyword lists below and AGENTS.md together, in the same diff.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
SRC = REPO_ROOT / "src" / "zrb"

# Named heavy third-party (or extras-marked) packages that justify category 1
# on their own, even without the literal phrase "heavy third-party".
HEAVY_PACKAGES = (
    "pydantic_ai",
    "prompt_toolkit",
    "mcp",
    "fastapi",
    "boto3",
    "anthropic",
    "openai",
    "chromadb",
    "playwright",
    "pdfplumber",
    "vosk",
    "fastmcp",
    "sounddevice",
    "numpy",
    "Pillow",
)

# Per-category counts as of this test landing. A change here must be a
# reviewed diff, same convention as CIRCULAR_IMPORT_ALLOWLIST in
# test_circular_import_allowlist.py.
EXPECTED_CATEGORY_COUNTS = {
    "circular": 6,
    "test_patch_seam": 23,
    "transitively_heavy_or_hot_path": 54,
    "heavy_third_party": 201,
}


def _clean(line: str) -> str:
    return line.strip().lstrip("#").strip()


def _classify_all() -> tuple[dict[str, int], list[str]]:
    counts = {key: 0 for key in EXPECTED_CATEGORY_COUNTS}
    uncategorized: list[str] = []
    for path in SRC.rglob("*.py"):
        lines = path.read_text().splitlines()
        i = 0
        while i < len(lines):
            if "# lazy:" not in lines[i]:
                i += 1
                continue
            block = [lines[i]]
            j = i + 1
            while j < len(lines):
                stripped = lines[j].strip()
                if stripped.startswith("#") and "# lazy:" not in lines[j]:
                    block.append(lines[j])
                    j += 1
                else:
                    break
            blocktext = " ".join(_clean(b) for b in block)
            location = f"{path.relative_to(SRC)}:{i + 1}"

            if "lazy: circular" in blocktext:
                counts["circular"] += 1
            elif re.search(r"tests?\s+patch", blocktext, re.IGNORECASE):
                counts["test_patch_seam"] += 1
            elif re.search(r"transitiv|hot[- ]path", blocktext, re.IGNORECASE):
                counts["transitively_heavy_or_hot_path"] += 1
            elif any(pkg in blocktext for pkg in HEAVY_PACKAGES) or (
                "heavy" in blocktext.lower()
            ):
                counts["heavy_third_party"] += 1
            else:
                uncategorized.append(f"{location}: {blocktext[:100]!r}")

            i = j if j > i + 1 else i + 1
    return counts, uncategorized


def test_every_lazy_import_states_a_recognized_reason():
    _, uncategorized = _classify_all()
    assert not uncategorized, (
        "These `# lazy:` comments don't state a reason this test recognizes "
        "(heavy third-party, transitively-heavy/hot-path internal, "
        "circular, or test-patch-seam). Reword the comment to state the "
        "real reason, or update this test's keyword lists and AGENTS.md's "
        "Imports section together if it's a genuinely new category:\n"
        + "\n".join(uncategorized)
    )


def test_lazy_import_category_counts_match_expected():
    counts, _ = _classify_all()
    assert counts == EXPECTED_CATEGORY_COUNTS, (
        "`# lazy:` category counts drifted from EXPECTED_CATEGORY_COUNTS — "
        "a comment was added, removed, or reclassified. Update "
        "EXPECTED_CATEGORY_COUNTS in this file to match, in the same diff, "
        f"with a reason.\nactual={counts}\nexpected={EXPECTED_CATEGORY_COUNTS}"
    )
