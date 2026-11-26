"""A call's `pattern` is a path only for the tools that join it onto one.

The gate read every `pattern` as a path, so `Grep(pattern="/home/user/.ssh")` —
a search for that literal text — was refused although ripgrep opens none of the
protected directory. A glob tool is the one that joins its pattern onto `path`,
and an absolute pattern replaces that path outright, so only a glob tool has its
pattern judged, and judged where it lands.
"""

from zrb.llm.capabilities.permission import Capability
from zrb.llm.capabilities.sandbox import SandboxPolicy
from zrb.llm.capabilities.sandbox.state import sandbox_policy
from zrb.llm.engine.agent.gates import sandbox_gate


def _policy(tmp_path, secrets) -> SandboxPolicy:
    return SandboxPolicy(
        enabled=True,
        writable_paths=(str(tmp_path / "proj"),),
        deny_read_paths=(str(secrets),),
    )


def test_a_greps_pattern_is_content_not_a_path(tmp_path):
    """The pattern names text to find, so it may spell a protected path."""
    project = tmp_path / "proj"
    project.mkdir()
    secrets = tmp_path / "secrets"
    secrets.mkdir()

    with sandbox_policy(_policy(tmp_path, secrets)):
        blocked = sandbox_gate(
            "Grep", Capability.READ, {"pattern": str(secrets), "path": str(project)}
        )

    assert blocked is None


def test_a_globs_pattern_is_judged_where_it_lands(tmp_path):
    """An absolute pattern replaces the searched directory, so it is refused."""
    project = tmp_path / "proj"
    project.mkdir()
    secrets = tmp_path / "secrets"
    secrets.mkdir()

    with sandbox_policy(_policy(tmp_path, secrets)):
        escaped = sandbox_gate(
            "Glob",
            Capability.READ,
            {"pattern": str(secrets / "*"), "path": str(project)},
        )
        inside = sandbox_gate(
            "Glob", Capability.READ, {"pattern": "**/*.py", "path": str(project)}
        )

    assert escaped is not None
    assert escaped.metadata.get("blocked") is True
    assert inside is None
