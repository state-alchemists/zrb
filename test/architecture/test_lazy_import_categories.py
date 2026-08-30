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

Deliberately NOT an exact-count ratchet (unlike
`CIRCULAR_IMPORT_ALLOWLIST` in `test_circular_import_allowlist.py`, which
this test originally copied that convention from). A first version asserted
per-category counts too, and it needed a manual update in nearly every
commit that touched a lazy import during the sweep that landed this file —
9 updates in one sitting, none of them catching anything the validity check
below didn't already catch. Ordinary reclassification (a comment moving
from "heavy third-party" to "transitively heavy") is neither rare nor
consequential the way a genuine new circular import is, so ratcheting it
was pure churn, not a safety margin. The count-based version is preserved
in git history if a future maintainer wants to revisit that trade-off.
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


def _clean(line: str) -> str:
    return line.strip().lstrip("#").strip()


def _is_categorized(blocktext: str) -> bool:
    if "lazy: circular" in blocktext:
        return True
    if re.search(r"tests?\s+patch", blocktext, re.IGNORECASE):
        return True
    if re.search(r"transitiv|hot[- ]path", blocktext, re.IGNORECASE):
        return True
    if any(pkg in blocktext for pkg in HEAVY_PACKAGES) or "heavy" in blocktext.lower():
        return True
    return False


def _find_uncategorized() -> list[str]:
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
            if not _is_categorized(blocktext):
                location = f"{path.relative_to(SRC)}:{i + 1}"
                uncategorized.append(f"{location}: {blocktext[:100]!r}")

            i = j if j > i + 1 else i + 1
    return uncategorized


def test_every_lazy_import_states_a_recognized_reason():
    uncategorized = _find_uncategorized()
    assert not uncategorized, (
        "These `# lazy:` comments don't state a reason this test recognizes "
        "(heavy third-party, transitively-heavy/hot-path internal, "
        "circular, or test-patch-seam). Reword the comment to state the "
        "real reason, or update this test's keyword lists and AGENTS.md's "
        "Imports section together if it's a genuinely new category:\n"
        + "\n".join(uncategorized)
    )
