"""Every record is reachable from its index, and carries one name and one number.

Two directories grow one file at a time and are read only through an index:
`docs/adr/` and `docs/changelog/`. A record that nobody links is invisible to
anyone scanning that index, and nothing could tell: the doc link checker proves
a link resolves, never that a file was listed. That asymmetry is why the index
tests exist — the failure they catch leaves no trace in either direction.

The naming and numbering tests below exist for a third failure, and they were
written because it happened: `0120-llm-layered-architecture.md` took a number
`adr-0120.md` had held for eight days, and broke the `adr-NNNN.md` name no
record had broken before. Every guard passed. The link pattern in
`test_architecture_docs.py` requires `adr-\d{4}\.md`, so the one file outside
the shape was the one file it never read; this module asked only whether each
record was *listed*, and both were. A directory that cannot state its own
naming rule will hold a second record under an old number again.
"""

import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).parents[2]
ADR_DIR = REPO_ROOT / "docs" / "adr"
CHANGELOG_DIR = REPO_ROOT / "docs" / "changelog"
BREADCRUMB = "🔖 [Documentation Home]"

# The shape a link to a record takes, so the shape a record's name must take.
ADR_FILE_NAME = re.compile(r"^adr-\d{4}\.md$")
# The number a record claims for itself. The title is what a reader cites in
# prose and the name is what a link resolves, so a record that disagrees with
# itself sends those two readers to different files.
ADR_TITLE = re.compile(r"^# ADR-(\d{4})\b", re.MULTILINE)


def _unlisted(directory: pathlib.Path, index: pathlib.Path) -> list[str]:
    """Records under *directory* whose filename never appears in *index*."""
    listed_text = index.read_text(encoding="utf-8")
    return [
        str(path.relative_to(REPO_ROOT))
        for path in sorted(directory.rglob("*.md"))
        if path != index and path.name != index.name and path.name not in listed_text
    ]


def _records() -> list[pathlib.Path]:
    """Every record in the directory, whatever shape its name is in.

    Deliberately not `adr-*.md`: a test that only reads well-named files
    cannot report the badly-named one that took a number, and that is the
    failure these tests were written for.
    """
    return [path for path in sorted(ADR_DIR.glob("*.md")) if path.name != "README.md"]


def _title_number(path: pathlib.Path) -> str | None:
    """The number *path* claims for itself in its title, if it claims one."""
    match = ADR_TITLE.search(path.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def test_every_adr_is_listed_in_the_adr_index():
    unlisted = _unlisted(ADR_DIR, ADR_DIR / "README.md")
    assert not unlisted, (
        "An ADR missing from docs/adr/README.md is invisible to a reader "
        "scanning the index. Add a row under the section it belongs to: "
        + ", ".join(unlisted)
    )


def test_every_adr_file_uses_the_house_name():
    """`README.md` and `adr-NNNN.md`, as every link to a record assumes."""
    offenders = [
        path.name
        for path in sorted(ADR_DIR.iterdir())
        if path.is_file()
        and path.name != "README.md"
        and not ADR_FILE_NAME.match(path.name)
    ]
    assert not offenders, (
        "An ADR outside `adr-NNNN.md` is invisible to the link pattern in "
        "test_architecture_docs.py, which requires that shape, and it sorts "
        "away from the records it belongs between. Rename it: " + ", ".join(offenders)
    )


def test_every_adr_number_matches_its_file_name():
    """The title is what a reader cites; the name is what a link resolves."""
    offenders = []
    for path in _records():
        if not ADR_FILE_NAME.match(path.name):
            continue  # the name test above owns a record named outside the shape
        title_number = _title_number(path)
        if title_number != path.name[4:8]:
            offenders.append(f"{path.name} opens as ADR-{title_number or 'nothing'}")
    assert not offenders, (
        "A record whose title and file name disagree sends the reader who "
        "cites its number to a different file than the one who follows its "
        "link: " + ", ".join(offenders)
    )


def test_no_two_adrs_share_a_number():
    """A number names one record, in prose, in a link and in an upgrade note."""
    seen: dict[str, str] = {}
    clashes = []
    for path in _records():
        number = _title_number(path)
        if number is None:
            continue  # the title test above owns a record with no number
        if number in seen:
            clashes.append(f"ADR-{number}: {seen[number]} and {path.name}")
        else:
            seen[number] = path.name
    assert not clashes, (
        "Two records answering to one number give a reader who follows that "
        "number whichever the index happens to place last. Renumber one of "
        "them, and say in it what it used to be called: " + "; ".join(clashes)
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
