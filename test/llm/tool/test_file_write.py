import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from zrb.llm.tool import file_observation
from zrb.llm.tool.file import (
    glob_files,
    list_files,
    read_file,
    replace_in_file,
    write_file,
)
from zrb.llm.tool.file_observation import clear_observed


@pytest.fixture(autouse=True)
def _reset_observed_state():
    """The observed-content map is a run-scoped module singleton — reset it
    so one test's Read/Write never leaks into another's assertions.
    """
    clear_observed()
    yield
    clear_observed()


@pytest.fixture
def run_scope():
    """Run the body under a named agent-run scope, restoring afterwards."""
    from zrb.llm.agent.run.runner import current_agent_run_scope

    def set_scope(name: str):
        return current_agent_run_scope.set(name)

    return set_scope


def _w(*a, **kw):
    return asyncio.run(write_file(*a, **kw))


def _r(*a, **kw):
    return asyncio.run(replace_in_file(*a, **kw))


@pytest.fixture(autouse=True)
def _no_real_lsp_server():
    """Keep write/replace tests from spawning a real LSP server subprocess.

    ``write_file``/``replace_in_file`` run post-write diagnostics on ``.py``
    files, which asks ``lsp_manager`` for a server. ``lsp_manager`` is a
    process-wide singleton, but each test here drives its coroutine through a
    throwaway ``asyncio.run()``, so a server spawned on one test's loop is
    reused after that loop is closed and never torn down — the child watcher
    then logs "Loop <...> that handles pid N is closed" once the process
    finally exits at interpreter shutdown. LSP integration itself is covered
    by test_post_write_check.py and test_lsp_tools.py; here it is stubbed out.
    """
    with patch(
        "zrb.llm.tool.post_write_check.lsp_manager.get_diagnostics",
        new=AsyncMock(return_value={"found": False, "diagnostics": []}),
    ):
        yield


def current_agent_run_scope_reset(token) -> None:
    from zrb.llm.agent.run.runner import current_agent_run_scope

    current_agent_run_scope.reset(token)


def test_replace_in_file_missing_directory_is_not_reported_as_a_missing_file(tmp_path):
    """A missing parent means a wrong path, so Write must not be suggested.

    Write creates missing parents, so following that advice turns a
    wrong-directory guess into a new tree and leaves the edit where nothing
    reads it.
    """
    result = _r(str(tmp_path / "nope" / "deeper" / "f.py"), "a", "b")

    assert "wrong path" in result.lower()
    assert "does not exist either" in result
    assert str(tmp_path / "nope" / "deeper") in result
    assert "Do not Write" in result


def test_replace_in_file_missing_file_in_existing_dir_still_suggests_write(tmp_path):
    """The original advice is right when only the file is absent."""
    result = _r(str(tmp_path / "absent.py"), "a", "b")

    assert "File not found" in result
    assert "use Write to create the" in result
    assert "wrong path" not in result.lower()


def test_write_file_reports_a_directory_it_created(tmp_path):
    """Creating a directory is a visible change, so the model is told."""
    target = tmp_path / "brand" / "new" / "f.txt"

    result = _w(str(target), "hello")

    assert "Successfully wrote" in result
    assert f"created new directory {tmp_path / 'brand' / 'new'}" in result
    assert target.read_text() == "hello"


def test_write_file_says_nothing_when_the_directory_existed(tmp_path):
    """No note for the ordinary case — it would be noise on every write."""
    result = _w(str(tmp_path / "f.txt"), "hello")

    assert "Successfully wrote" in result
    assert "created new directory" not in result


def test_write_file_blocks_overwrite_of_unread_existing_file(tmp_path):
    file_path = tmp_path / "f.txt"
    file_path.write_text("original, written outside this run")

    result = _w(str(file_path), "clobbered")

    assert "Error" in result
    assert "has not been read in this session" in result
    assert file_path.read_text() == "original, written outside this run"


def test_write_file_allows_overwrite_after_read(tmp_path):
    file_path = tmp_path / "f.txt"
    file_path.write_text("original")

    read_file(str(file_path))
    result = _w(str(file_path), "updated")

    assert "Successfully wrote" in result
    assert file_path.read_text() == "updated"


def test_write_file_blocks_overwrite_when_content_changed_after_read(tmp_path):
    file_path = tmp_path / "f.txt"
    file_path.write_text("original")

    read_file(str(file_path))
    file_path.write_text("changed by something else")  # bypasses our tools
    result = _w(str(file_path), "clobbered")

    assert "Error" in result
    assert "has changed since it was last read" in result
    assert file_path.read_text() == "changed by something else"


def test_write_file_allows_overwrite_of_new_file_without_reading_first(tmp_path):
    file_path = tmp_path / "brand-new.txt"

    result = _w(str(file_path), "hello")

    assert "Successfully wrote" in result
    assert file_path.read_text() == "hello"


def test_write_file_allows_second_write_without_an_intervening_read(tmp_path):
    """Write itself counts as observation — no special-casing "last tool
    used" needed, the recorded hash is just refreshed after every write.
    """
    file_path = tmp_path / "f.txt"

    _w(str(file_path), "first")
    result = _w(str(file_path), "second")

    assert "Successfully wrote" in result
    assert file_path.read_text() == "second"


def test_write_file_chunked_append_then_rewrite_is_allowed(tmp_path):
    """The documented mode="w" then mode="a" workflow must not leave a stale
    hash that blocks a later legitimate mode="w" rewrite by the same run.
    """
    file_path = tmp_path / "f.txt"

    _w(str(file_path), "part1")
    _w(str(file_path), "part2", mode="a")
    result = _w(str(file_path), "rewritten from scratch")

    assert "Successfully wrote" in result
    assert file_path.read_text() == "rewritten from scratch"


def test_write_file_append_to_existing_unread_file_is_not_blocked(tmp_path):
    """mode="a" is non-destructive to existing content, so it skips the gate
    entirely — only mode="w" against a pre-existing file is checked.
    """
    file_path = tmp_path / "f.txt"
    file_path.write_text("original, never read by this run")

    result = _w(str(file_path), " appended", mode="a")

    assert "Successfully wrote" in result
    assert file_path.read_text() == "original, never read by this run appended"


def test_replace_in_file_does_not_require_a_prior_read(tmp_path):
    """Edit is not gated by the observed-hash check — it already verifies
    old_text against live on-disk content at call time.
    """
    file_path = tmp_path / "f.txt"
    file_path.write_text("hello world")

    result = _r(str(file_path), "world", "zrb")

    assert "Successfully" in result
    assert file_path.read_text() == "hello zrb"


def test_observed_map_evicts_the_least_recently_used_scope(
    tmp_path, run_scope, monkeypatch
):
    """Every delegation mints a fresh scope that outlives its run, so the
    map is LRU-capped. Eviction fails safe: the evicted scope's next
    overwrite is refused with a pointer back to Read, never allowed.
    """
    from zrb.llm.tool.file_observation import record_observed

    monkeypatch.setattr(file_observation, "MAX_OBSERVED_SCOPES", 2)

    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    third = tmp_path / "third.txt"
    for path in (first, second, third):
        path.write_text("original")

    # Three scopes recorded in order; the cap is 2, so s1 (the least
    # recently used) is evicted when s3 arrives and {s2, s3} remain.
    tokens = {}
    for name, path in (("s1", first), ("s2", second), ("s3", third)):
        token = run_scope(name)
        tokens[name] = token
        read_file(str(path))
        record_observed(str(path), path.read_text())
        current_agent_run_scope_reset(token)

    # Each overwrite runs under the scope that did the reading — a write
    # under any other scope (including none) must be refused regardless.
    results = {}
    for name, path in (("s1", first), ("s2", second), ("s3", third)):
        token = run_scope(name)
        results[name] = _w(str(path), "clobbered")
        current_agent_run_scope_reset(token)

    assert "has not been read in this session" in results["s1"]
    assert "Successfully wrote" in results["s2"]
    assert "Successfully wrote" in results["s3"]


def test_observed_map_treats_a_check_as_a_use_of_its_scope(
    tmp_path, run_scope, monkeypatch
):
    """An active conversation must not be evicted out from under itself by
    delegations sharing the process: a blocked-write check under a scope
    refreshes its recency just like a recording does.
    """
    from zrb.llm.tool.file_observation import (
        check_observed,
        record_observed,
    )

    monkeypatch.setattr(file_observation, "MAX_OBSERVED_SCOPES", 2)

    watched = tmp_path / "watched.txt"
    filler_a = tmp_path / "filler-a.txt"
    filler_b = tmp_path / "filler-b.txt"
    for path in (watched, filler_a, filler_b):
        path.write_text("content")

    # The watched scope records one file; another scope lands after it,
    # pushing watched toward the eviction end.
    token = run_scope("watched")
    record_observed(str(watched), watched.read_text())
    current_agent_run_scope_reset(token)
    token = run_scope("filler-a")
    read_file(str(filler_a))
    current_agent_run_scope_reset(token)

    # A check under the watched scope refreshes its recency...
    token = run_scope("watched")
    assert check_observed(str(watched)) is None
    current_agent_run_scope_reset(token)

    # ...so when one more scope arrives and forces an eviction, the older
    # `filler-a` scope is dropped and the watched scope survives — without
    # the touch above, it would have been the one evicted here.
    token = run_scope("filler-b")
    read_file(str(filler_b))
    current_agent_run_scope_reset(token)

    token = run_scope("watched")
    result = _w(str(watched), "updated")
    current_agent_run_scope_reset(token)
    assert "Successfully wrote" in result


def test_check_listed_refuses_an_unread_unlisted_file(tmp_path):
    from zrb.llm.tool.file_observation import check_listed

    target = tmp_path / "victim.txt"
    target.write_text("content")
    result = check_listed(str(target), recursive=False)
    assert result is not None
    assert "has not been read or listed" in result


def test_check_listed_allows_a_file_shown_by_list_files(tmp_path):
    from zrb.llm.tool.file_observation import check_listed

    target = tmp_path / "victim.txt"
    target.write_text("content")
    list_files(str(tmp_path))
    assert check_listed(str(target), recursive=False) is None


def test_check_listed_allows_a_file_shown_by_glob_files(tmp_path):
    from zrb.llm.tool.file_observation import check_listed

    target = tmp_path / "victim.txt"
    target.write_text("content")
    glob_files("*.txt", str(tmp_path))
    assert check_listed(str(target), recursive=False) is None


def test_check_listed_allows_a_file_already_read(tmp_path):
    """A Read satisfies the lighter listed-bar too — no need to also List."""
    from zrb.llm.tool.file_observation import check_listed

    target = tmp_path / "victim.txt"
    target.write_text("content")
    read_file(str(target))
    assert check_listed(str(target), recursive=False) is None


def test_check_listed_refuses_an_unlisted_directory_recursively(tmp_path):
    from zrb.llm.tool.file_observation import check_listed

    sub = tmp_path / "sub"
    sub.mkdir()
    result = check_listed(str(sub), recursive=True)
    assert result is not None
    assert "has not been listed" in result


def test_check_listed_allows_a_listed_directory_recursively(tmp_path):
    from zrb.llm.tool.file_observation import check_listed

    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "a.txt").write_text("a")
    list_files(str(sub))
    assert check_listed(str(sub), recursive=True) is None


def test_check_listed_refuses_a_directory_that_changed_since_listing(tmp_path):
    """The staleness re-check: a top-level entry added after listing must
    still be caught, mirroring check_observed's own drift detection."""
    from zrb.llm.tool.file_observation import check_listed

    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "a.txt").write_text("a")
    list_files(str(sub))
    (sub / "b.txt").write_text("b")
    result = check_listed(str(sub), recursive=True)
    assert result is not None
    assert "changed since it was listed" in result


def test_replace_in_file_does_not_require_a_prior_read(tmp_path):
    """Edit is not gated by the observed-hash check — it already verifies
    old_text against live on-disk content at call time.
    """
    file_path = tmp_path / "f.txt"
    file_path.write_text("hello world")

    result = _r(str(file_path), "world", "zrb")

    assert "Successfully" in result
    assert file_path.read_text() == "hello zrb"


def test_replace_in_file_then_write_overwrite_is_allowed(tmp_path):
    """Edit also refreshes the observed hash, so a follow-up mode="w" by the
    same run doesn't need a separate Read.
    """
    file_path = tmp_path / "f.txt"
    file_path.write_text("hello world")

    _r(str(file_path), "world", "zrb")
    result = _w(str(file_path), "fully replaced")

    assert "Successfully wrote" in result
    assert file_path.read_text() == "fully replaced"


def test_replace_in_file_already_applied_edit_says_so(tmp_path):
    """A fuzzy match onto text that already equals new_text is a landed edit.

    old_text differs from new_text only in trailing whitespace, so the fuzzy
    matcher lands on a region that already reads exactly as new_text.
    """
    file_path = tmp_path / "test.txt"
    file_path.write_text("foo bar\n")

    result = _r(str(file_path), "foo bar ", "foo bar\n")

    assert "already applied" in result
    assert "are identical" not in result
    assert "Do not repeat this call" in result


def test_replace_in_file_zero_count_names_count_as_the_cause(tmp_path):
    """count=0 is a no-op the model fixes by changing count, not the text."""
    file_path = tmp_path / "test.txt"
    file_path.write_text("hello world")

    result = _r(str(file_path), "hello", "HELLO", count=0)

    assert "count=0" in result
    assert "count=1" in result
    assert file_path.read_text() == "hello world"


def test_replace_in_file_near_match(tmp_path):
    file_path = tmp_path / "test.txt"
    file_path.write_text("hello world\ngoodbye world\n")

    # old_text first line ("hello worl") is a substring of file line but full old_text doesn't match
    result = _r(str(file_path), "hello worl\ngoodbye", "hello zrb")
    assert "not found" in result.lower()
    assert "Similar lines found" in result


def test_replace_in_file_fuzzy_trailing_whitespace(tmp_path):
    """Fuzzy match should succeed when file lines have trailing whitespace."""
    file_path = tmp_path / "test.txt"
    file_path.write_text("hello world   \ngoodbye world   \n")

    # old_text has no trailing whitespace, file has trailing spaces
    result = _r(str(file_path), "hello world\ngoodbye world", "hi there")
    assert "Successfully updated" in result
    assert "fuzzy match" in result.lower()
    assert "hi there" in file_path.read_text()


def test_replace_in_file_fuzzy_indentation_flexible(tmp_path):
    """Fuzzy match should succeed when indentation differs by a common prefix."""
    file_path = tmp_path / "test.py"
    file_path.write_text("    def foo():\n        pass\n")

    # old_text uses a different but consistent indentation level
    result = _r(str(file_path), "def foo():\n    pass", "def bar():\n    return 1")
    assert "Successfully updated" in result
    assert "fuzzy match" in result.lower()
    content = file_path.read_text()
    assert "bar" in content


def test_replace_in_file_multiple_matches(tmp_path):
    file_path = tmp_path / "test.txt"
    file_path.write_text("foo bar foo baz")

    # Without count, replaces all
    result = _r(str(file_path), "foo", "FOO")
    assert "Successfully updated" in result
    with open(file_path) as f:
        assert f.read() == "FOO bar FOO baz"

    # With count=1, replaces first only
    file_path.write_text("foo bar foo baz")
    result = _r(str(file_path), "foo", "FOO", count=1)
    assert "Successfully updated" in result
    with open(file_path) as f:
        assert f.read() == "FOO bar foo baz"
