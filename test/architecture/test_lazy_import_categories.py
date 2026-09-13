"""Every `# lazy:` comment must state a reason this test can classify.

AGENTS.md (Imports) allows five: heavy third-party deferral,
transitively-heavy-via-internal (which absorbs hot-path avoidance of an
internal import — same concern, keyed to call frequency), circular import,
test-patch seam, platform-only module. A comment matching none of them fails
here, and the fix is to reword it to its real reason — or, if the reason is
genuinely new, to extend the keyword lists below and AGENTS.md together.

Validity only, deliberately not a per-category count ratchet: reclassifying a
comment between categories is routine and catches nothing the validity check
misses, unlike `CIRCULAR_IMPORT_ALLOWLIST`, where a new entry is the signal.
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
    if re.search(r"platform[- ]only", blocktext, re.IGNORECASE):
        return True
    if any(pkg in blocktext for pkg in HEAVY_PACKAGES) or "heavy" in blocktext.lower():
        return True
    return False


def _find_uncategorized() -> list[str]:
    uncategorized: list[str] = []
    for path in SRC.rglob("*.py"):
        lines = path.read_text(encoding="utf-8").splitlines()
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
        "circular, test-patch-seam, or platform-only). Reword the comment "
        "to state the "
        "real reason, or update this test's keyword lists and AGENTS.md's "
        "Imports section together if it's a genuinely new category:\n"
        + "\n".join(uncategorized)
    )
