"""Which notes a session is shown, by the repository it is working in.

Memory that arrives naturally is memory about *here*. A note on how one
repository's CI fails is noise in the next repository: the index has one line
per note, so a single checkout's worth of notes crowds out everything else, and
the reader has to search to find out what is left.

The rule is one field and one filter:

- a note carries ``repo: <tag>`` when it is about one repository, and nothing
  when it is about no place in particular — who the user is, how they want to be
  spoken to, what the agent itself prefers;
- the injected index, the per-turn claims and the auto-search show a note when
  its tag is empty, ``global``, or the repository in hand;
- ``SearchJournal`` is never filtered. Scoping is about what arrives unasked,
  not about what can be found.

A note with no tag is shown everywhere, deliberately: the field is new, and a
default that guessed would hide three hundred notes at once.
"""

import os
import re

GLOBAL_SCOPE = "global"
"""The tag a note carries when it is about no one repository."""

WORK_SCOPED_CATEGORIES = ("projects", "technical")
"""Categories whose notes are usually about a place.

Their default is the repository in hand. The other three describe the user or
the agent themselves, and travel with the person rather than the checkout."""

_SCOPE_RE = re.compile(r"[^a-z0-9._-]+")


def normalize_scope(repo: str) -> str:
    """*repo* as one tag: lower case, letters, digits, `.`, `-`, `_`.

    The tag is compared against a directory name and stored inside one
    frontmatter line, so it may contain neither whitespace nor a newline."""
    tag = _SCOPE_RE.sub("-", repo.strip().lower()).strip("-")
    return "" if tag == GLOBAL_SCOPE else tag


def default_scope(category: str, repo: str) -> str:
    """The tag a note in *category* gets when its caller names none."""
    if category not in WORK_SCOPED_CATEGORIES:
        return ""
    return normalize_scope(repo)


def is_in_scope(note_repo: str, current: str) -> bool:
    """Whether a note tagged *note_repo* is shown while working in *current*.

    An untagged note is shown everywhere, and so is every note when there is no
    repository in hand — a chat opened outside a checkout has no better filter
    than none, and hiding the journal there would be the opposite of memory."""
    if not note_repo or not current:
        return True
    return note_repo == normalize_scope(current)


def repo_of(path: str) -> str:
    """The tag for the repository at *path*: its top-level directory's name."""
    from zrb.llm.util.git import repository_name  # lazy: hot-path internal — pulls CFG

    return normalize_scope(repository_name(path))


def repo_root(path: str) -> str:
    """The top-level directory of the repository at *path*, or ``""``."""
    from zrb.llm.util.git import repository_root

    return repository_root(path)


def scope_for_source(source: str, root: str) -> str:
    """The repository a note's ``source`` points into, or ``""`` when it cannot say.

    A note that cites ``src/zrb/llm/tool/journal_note.py:52`` is about the
    checkout that file lives in; one that cites a commit hash, a version or a
    URL is about something else and stays untagged until its author says."""
    if not source or not root:
        return ""
    cited = source.strip().split()[0].split(":")[0]
    if os.path.isabs(cited):
        return ""
    if not os.path.exists(os.path.join(root, cited)):
        return ""
    return repo_of(root)
