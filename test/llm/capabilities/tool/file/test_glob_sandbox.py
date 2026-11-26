"""Every file `Glob` lists is judged, not only the arguments it was given.

The gate reads `path` and the raw `pattern`, and neither of them is the file:
`Glob` joins the two itself, so a symlinked segment of the pattern reaches a
deny-read root the gate never saw, and `glob` returns the match spelled as if it
were inside the searched directory. `Grep` and `AnalyzeCode` already judge each
file they open; `Glob` listed whatever it found.
"""

from __future__ import annotations

from zrb.llm.capabilities.sandbox import SandboxPolicy, sandbox_policy
from zrb.llm.capabilities.tool.file import glob_files


def _sandboxed(project, deny_dir, enabled=True):
    return sandbox_policy(
        SandboxPolicy(
            enabled=enabled,
            writable_paths=(str(project),),
            deny_read_paths=(str(deny_dir),),
        )
    )


def _project_with_a_symlink(tmp_path):
    """A searched directory holding `link`, which points at the secrets."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "keep.txt").write_text("x")
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (secrets / "id_rsa").write_text("PRIVATE")
    (project / "link").symlink_to(secrets)
    return project, secrets


def test_a_symlinked_segment_of_the_pattern_does_not_list_a_deny_root(tmp_path):
    """The gate judged `path`, which is outside; the join went through the link."""
    project, secrets = _project_with_a_symlink(tmp_path)

    with _sandboxed(project, secrets):
        result = glob_files("link/*", path=str(project), include_hidden=True)

    assert result.get("files") == []
    assert "PRIVATE" not in repr(result)
    assert "deny-read" in str(result["warning"])


def test_a_symlinked_file_match_is_left_out(tmp_path):
    """The link can be the match itself, not only a segment of the pattern."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "keep.txt").write_text("x")
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (secrets / "id_rsa").write_text("PRIVATE")
    (project / "innocent.txt").symlink_to(secrets / "id_rsa")

    with _sandboxed(project, secrets):
        result = glob_files("**/*.txt", path=str(project))

    assert result.get("files") == ["keep.txt"]
    assert "PRIVATE" not in repr(result)
    assert "deny-read" in str(result["warning"])


def test_a_match_outside_every_deny_root_is_listed_unchanged(tmp_path):
    """The filter drops two kinds of match, not every match."""
    project, secrets = _project_with_a_symlink(tmp_path)

    with _sandboxed(project, secrets):
        result = glob_files("*.txt", path=str(project))

    assert result.get("files") == ["keep.txt"]
    assert "warning" not in result


def test_a_disabled_policy_lists_through_the_symlink(tmp_path):
    """Containment off is the no-sandbox path: the link is followed as before."""
    project, secrets = _project_with_a_symlink(tmp_path)

    with _sandboxed(project, secrets, enabled=False):
        result = glob_files("link/*", path=str(project))

    assert result.get("files") == ["link/id_rsa"]
    assert "warning" not in result
