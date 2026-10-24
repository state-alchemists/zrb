"""Every record is reachable from its index.

Two directories grow one file at a time and are read only through an index:
`docs/adr/` and `docs/changelog/`. A record that nobody links is invisible to
anyone scanning that index, and nothing could tell: the doc link checker proves
a link resolves, never that a file was listed. That asymmetry is why this test
exists — the failure it catches leaves no trace in either direction.
"""

import pathlib

REPO_ROOT = pathlib.Path(__file__).parents[2]
ADR_DIR = REPO_ROOT / "docs" / "adr"
CHANGELOG_DIR = REPO_ROOT / "docs" / "changelog"
BREADCRUMB = "🔖 [Documentation Home]"


def _unlisted(directory: pathlib.Path, index: pathlib.Path) -> list[str]:
    """Records under *directory* whose filename never appears in *index*."""
    listed_text = index.read_text(encoding="utf-8")
    return [
        str(path.relative_to(REPO_ROOT))
        for path in sorted(directory.rglob("*.md"))
        if path != index and path.name != index.name and path.name not in listed_text
    ]


def test_every_adr_is_listed_in_the_adr_index():
    unlisted = _unlisted(ADR_DIR, ADR_DIR / "README.md")
    assert not unlisted, (
        "An ADR missing from docs/adr/README.md is invisible to a reader "
        "scanning the index. Add a row under the section it belongs to: "
        + ", ".join(unlisted)
    )


def test_every_changelog_file_is_listed_in_the_changelog_index():
    unlisted = _unlisted(CHANGELOG_DIR, CHANGELOG_DIR / "README.md")
    assert not unlisted, (
        "A changelog file missing from docs/changelog/README.md cannot be "
        "found by a reader looking for that release: " + ", ".join(unlisted)
    )


def test_every_changelog_file_opens_with_the_breadcrumb():
    """The first line is the way back out of a long release note."""
    wrong = [
        str(path.relative_to(REPO_ROOT))
        for path in sorted(CHANGELOG_DIR.rglob("*.md"))
        if path.name != "README.md"
        and not path.read_text(encoding="utf-8").startswith(BREADCRUMB)
    ]
    assert not wrong, (
        "A changelog file must open with its breadcrumb, as every other page "
        "does, so a reader who lands mid-file can leave: " + ", ".join(wrong)
    )
