"""The HUD template must produce a journal that `journal-lint.py` accepts.

The template prescribes the root `index.md`, and the same skill ships a linter
whose NO ORPHANS check measures reachability *from that file*. Those two can
disagree silently: a template with no directory links reads fine and lints as
one orphan per top-level directory. It did, once — every fresh journal opened
with a lint failure the model then had to improvise around. This pins them
together, so editing the template's example without keeping the tree reachable
fails here instead of in someone's first session.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

SKILL_DIR = (
    Path(__file__).resolve().parents[2]
    / "src/zrb/llm_plugin/core_skills/core-journaling"
)
TEMPLATE = SKILL_DIR / "templates/journal-index.md"
LINT_TOOL = SKILL_DIR / "tools/journal-lint.py"

TOP_LEVEL_DIRS = ("user", "preferences", "projects", "technical", "activity-log")
LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")


def _lint(root: Path) -> str:
    """Run the linter exactly as `SKILL.md` tells the model to run it."""
    return subprocess.run(
        [sys.executable, str(LINT_TOOL), str(root)],
        capture_output=True,
        text=True,
    ).stdout


def _example_hud() -> str:
    """The last fenced block in the template — the worked example."""
    blocks = re.findall(r"````markdown\n(.*?)````", TEMPLATE.read_text("utf-8"), re.S)
    assert blocks, "template has no fenced markdown block"
    return blocks[-1]


def _materialize(root: Path, hud: str) -> None:
    """Write the HUD plus every file it links to, so the graph is complete."""
    (root / "index.md").write_text(hud, encoding="utf-8")
    for _, target in LINK_RE.findall(hud):
        if "://" in target or target.startswith("#"):
            continue
        path = root / target
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.name == "index.md":
            # Directory indexes are exempt from the backlink requirement.
            path.write_text(f"# {path.parent.name}\n", encoding="utf-8")
        else:
            up = "../" * len(path.relative_to(root).parts[:-1])
            path.write_text(
                f"# {path.stem}\n\n## Backlinks\n- [root]({up}index.md) — HUD\n",
                encoding="utf-8",
            )


@pytest.mark.parametrize("directory", TOP_LEVEL_DIRS)
def test_example_hud_links_every_top_level_directory(directory):
    targets = {t for _, t in LINK_RE.findall(_example_hud())}
    assert f"{directory}/index.md" in targets


def test_journal_built_from_the_template_lints_clean(tmp_path):
    _materialize(tmp_path, _example_hud())

    assert "is clean" in _lint(tmp_path)


def test_lint_still_catches_a_hud_that_drops_the_directory_links(tmp_path):
    """Guards the guard: the test above must fail for the reason we think."""
    hud = _example_hud()
    _materialize(tmp_path, hud)
    stripped = re.sub(r"## Directories\n\n.*?\n\n", "", hud, flags=re.S)
    (tmp_path / "index.md").write_text(stripped, encoding="utf-8")

    output = _lint(tmp_path)

    assert "[orphan]" in output
    assert "user/index.md" in output
