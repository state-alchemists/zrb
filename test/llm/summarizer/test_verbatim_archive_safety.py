"""The archive's write boundary: who may read it, what it refuses, and what a
failed write leaves behind.

The archive holds a conversation word for word, so it is created owner-only and
never written through a symlink; an append that fails partway is cut back to the
length it started at rather than left as a half-written section.
"""

import logging
import os
import stat
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)

from zrb.config.config import CFG
from zrb.llm.summarizer import verbatim_archive
from zrb.llm.summarizer.verbatim_archive import (
    archive_verbatim_history,
    verbatim_archive_path,
)

# `os.chmod` on Windows toggles only the read-only flag, and a directory there
# reports 0o777 whatever mode it was created with, so the private-mode guarantee
# is POSIX-only. The rollback guarantee is not.
needs_posix_modes = pytest.mark.skipif(
    os.name != "posix", reason="POSIX permission bits (the mode under test)"
)

# `O_NOFOLLOW` is a POSIX flag; Windows has no equivalent, and creating a symlink
# there needs a privilege a hijack would first have to win.
needs_no_follow = pytest.mark.skipif(
    os.name != "posix", reason="O_NOFOLLOW (refusing a symlinked archive)"
)


def _messages():
    return [
        ModelRequest(parts=[UserPromptPart(content="fix the parser")]),
        ModelResponse(parts=[TextPart(content="Looking at it.")]),
        ModelRequest(parts=[UserPromptPart(content="and now?")]),
        ModelResponse(parts=[TextPart(content="Done.")]),
    ]


def _read(path):
    with open(path, encoding="utf-8") as stream:
        return stream.read()


def _symlink(link, target):
    try:
        os.symlink(target, link)
    except OSError as error:
        # Windows needs SeCreateSymbolicLinkPrivilege or Developer Mode to create
        # one; without it there is no attack here to reproduce.
        pytest.skip(f"cannot create a symlink on this platform: {error}")


class _PartialWriteStream:
    """A stream that reaches partway through the text, then fails to write.

    Stands in for the `ENOSPC` an archive write can hit, without a full disk. It
    is a file object, so the code under test keeps its own flush-and-close path.
    """

    def __init__(self, stream, written_chars):
        self._stream = stream
        self._written_chars = written_chars

    def __enter__(self):
        return self

    def __exit__(self, *exception_info):
        # The descriptor was handed over with `closefd=False`: the caller must
        # still be able to truncate the file it was writing to.
        self._stream.close()
        return False

    def write(self, text):
        self._stream.write(text[: self._written_chars])
        self._stream.flush()
        raise OSError(28, "No space left on device")


class _FailingAppendOs:
    """The module's `os`, with the append made to fail partway.

    The seam is the filesystem boundary: the public archive function is driven,
    and the assertion is on the file the failed write left behind.
    """

    def __init__(self, written_chars, rollback_fails=False):
        self._written_chars = written_chars
        self._rollback_fails = rollback_fails

    def __getattr__(self, name):
        return getattr(os, name)

    def fdopen(self, descriptor, mode, **kwargs):
        stream = os.fdopen(descriptor, mode, **kwargs)
        return _PartialWriteStream(stream, self._written_chars)

    def ftruncate(self, descriptor, size):
        if self._rollback_fails:
            raise OSError(5, "Input/output error")
        os.ftruncate(descriptor, size)


@needs_posix_modes
def test_a_new_archive_is_private_to_its_owner(tmp_path):
    """A transcript is as private as the conversation it came from: the
    directory is 0700 and the file 0600, whatever the umask."""
    path = verbatim_archive_path("private", str(tmp_path))

    assert archive_verbatim_history(_messages(), path=path) == path

    assert stat.S_IMODE(os.stat(os.path.dirname(path)).st_mode) == 0o700
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


@needs_posix_modes
def test_an_existing_archive_is_narrowed_once(tmp_path):
    """An archive written before the private-mode rule was readable by others.
    It is narrowed in place on first use, and the marker keeps that from being
    a blanket permission change on every later run."""
    from zrb.util.owner_only import marker_path

    path = verbatim_archive_path("old", str(tmp_path))
    os.makedirs(os.path.dirname(path))
    os.chmod(os.path.dirname(path), 0o755)
    with open(path, "w", encoding="utf-8") as stream:
        stream.write("## Compacted earlier — 1 message(s)\n")
    os.chmod(path, 0o644)
    assert not os.path.exists(marker_path(os.path.dirname(path)))

    assert archive_verbatim_history(_messages(), path=path) == path

    assert stat.S_IMODE(os.stat(os.path.dirname(path)).st_mode) == 0o700
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert os.path.exists(marker_path(os.path.dirname(path)))


@needs_posix_modes
def test_a_narrowed_archive_is_not_walked_again(tmp_path):
    """The marker is the whole point: a file the user made readable again after
    the migration stays as they left it, because zrb is not entitled to change
    a mode on every run."""
    from zrb.util.owner_only import marker_path

    path = verbatim_archive_path("again", str(tmp_path))
    assert archive_verbatim_history(_messages(), path=path) == path
    os.chmod(path, 0o644)

    assert archive_verbatim_history(_messages(), path=path) == path

    assert stat.S_IMODE(os.stat(path).st_mode) == 0o644
    assert os.path.exists(marker_path(os.path.dirname(path)))


@needs_no_follow
def test_a_symlinked_archive_is_refused(tmp_path, caplog):
    """A link planted where the archive belongs must not take the append: the
    transcript would land in a file of the planter's choosing."""
    victim = tmp_path / "victim.md"
    victim.write_text("untouched", encoding="utf-8")
    path = verbatim_archive_path("hijacked", str(tmp_path))
    os.makedirs(os.path.dirname(path))
    _symlink(path, str(victim))

    with caplog.at_level(logging.WARNING):
        assert archive_verbatim_history(_messages(), path=path) is None

    assert victim.read_text(encoding="utf-8") == "untouched"
    assert "Could not archive verbatim history" in caplog.text


def test_a_symlinked_archive_directory_is_refused(tmp_path, caplog):
    """`makedirs(exist_ok=True)` follows a symlinked directory; the archive
    would then be written wherever that link points."""
    outside = tmp_path / "outside"
    outside.mkdir()
    base = tmp_path / "history"
    base.mkdir()
    _symlink(base / "verbatim", str(outside))
    path = verbatim_archive_path("hijacked", str(base))

    with caplog.at_level(logging.WARNING):
        assert archive_verbatim_history(_messages(), path=path) is None

    assert list(outside.iterdir()) == []
    assert "not a directory" in caplog.text


def test_a_failed_append_leaves_the_archive_as_it_was(tmp_path, monkeypatch):
    """The bytes past the pre-write size are this call's own, so cutting back
    there removes exactly the half-written section and nothing else."""
    path = verbatim_archive_path("s", str(tmp_path))
    assert archive_verbatim_history(_messages()[:1], path=path) == path
    before = _read(path)

    monkeypatch.setattr(verbatim_archive, "os", _FailingAppendOs(written_chars=40))

    assert archive_verbatim_history(_messages()[1:2], path=path) is None
    assert _read(path) == before


def test_a_failed_first_append_leaves_no_header_behind(tmp_path, monkeypatch):
    """A new file whose only bytes are a header reads as an archive of nothing;
    the next attempt must start clean instead."""
    path = verbatim_archive_path("fresh", str(tmp_path))
    with monkeypatch.context() as failing:
        failing.setattr(verbatim_archive, "os", _FailingAppendOs(written_chars=10))
        assert archive_verbatim_history(_messages(), path=path) is None
    assert _read(path) == ""

    assert archive_verbatim_history(_messages(), path=path) == path
    text = _read(path)
    assert text.startswith("# Verbatim history — fresh")
    assert text.count("# Verbatim history") == 1
    assert text.count("## Compacted ") == 1


def test_a_write_that_cannot_be_rolled_back_keeps_the_partial_section(
    tmp_path, monkeypatch, caplog
):
    """The residual risk, pinned rather than hidden: when the truncate fails too
    the partial bytes stay. The call still returns None, so no summary is pointed
    at the damaged file."""
    path = verbatim_archive_path("s", str(tmp_path))
    assert archive_verbatim_history(_messages()[:1], path=path) == path
    before = _read(path)

    monkeypatch.setattr(
        verbatim_archive, "os", _FailingAppendOs(written_chars=40, rollback_fails=True)
    )
    with caplog.at_level(logging.WARNING):
        assert archive_verbatim_history(_messages()[1:2], path=path) is None

    after = _read(path)
    assert after.startswith(before)
    assert after != before
    assert "Could not roll back a partial archive write" in caplog.text


@pytest.mark.asyncio
async def test_a_refused_write_gives_the_summary_no_pointer(tmp_path, monkeypatch):
    """The end-to-end contract, driven by a real refusal rather than a patched
    return value: the summary must not name a file nothing was written to."""
    monkeypatch.setattr(CFG, "LLM_HISTORY_DIR", str(tmp_path), raising=False)
    path = verbatim_archive_path("hijacked", str(tmp_path))
    os.makedirs(os.path.dirname(path))
    victim = tmp_path / "victim.md"
    victim.write_text("untouched", encoding="utf-8")
    _symlink(path, str(victim))
    agent = MagicMock()
    agent.run = AsyncMock(return_value=MagicMock(output="Summary content"))

    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.summarizer import summarize_history

    new_history = await summarize_history(
        _messages(),
        agent=agent,
        summary_window=1,
        conversational_token_threshold=10,
        session_name="hijacked",
    )

    summary_text = str(getattr(new_history[0].parts[0], "content", ""))
    assert "Summary content" in summary_text  # the compaction still happened
    assert "## Verbatim history archive" not in summary_text
    assert path not in summary_text
    assert victim.read_text(encoding="utf-8") == "untouched"


def test_a_busy_archive_returns_no_pointer(tmp_path, caplog):
    """Another process holding the archive's lock must not cost the caller an
    exception, and must not produce a pointer to a section never written. The
    warning names the lock and the setting, so a human and the log can tell a
    busy archive from a broken one."""
    from zrb.util.file_lock import FileLockTimeout

    path = verbatim_archive_path("busy", str(tmp_path))

    with patch(
        "zrb.llm.summarizer.verbatim_archive.hold_file_lock",
        side_effect=FileLockTimeout("held elsewhere"),
    ):
        with caplog.at_level(logging.WARNING):
            assert archive_verbatim_history(_messages(), path=path) is None

    assert not os.path.exists(path)
    assert "another writer held its lock" in caplog.text
    assert "LLM_ARCHIVE_LOCK_TIMEOUT" in caplog.text
    assert "carries no archive pointer" in caplog.text


def test_the_append_waits_the_configured_lock_timeout(tmp_path, monkeypatch):
    """`LLM_ARCHIVE_LOCK_TIMEOUT` is the wait; a fixed number would ignore it."""
    from zrb.util.file_lock import hold_file_lock

    monkeypatch.setattr(CFG, "LLM_ARCHIVE_LOCK_TIMEOUT", 7.5, raising=False)
    path = verbatim_archive_path("timed", str(tmp_path))

    with patch(
        "zrb.llm.summarizer.verbatim_archive.hold_file_lock", wraps=hold_file_lock
    ) as lock:
        archive_verbatim_history(_messages(), path=path)

    assert lock.call_args.kwargs["timeout"] == 7.5
