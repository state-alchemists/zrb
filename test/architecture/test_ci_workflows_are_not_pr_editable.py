"""A workflow cannot be rewritten by the pull request it runs for.

GitHub resolves a `pull_request` workflow — and every local `uses:` inside it —
from the pull request's *merge commit*. A branch that edits the file therefore
gets its edits executed, with whatever secrets the job declares, before anyone
reviews the diff. `pull_request_target` resolves the same files from the base
branch instead, which a pull request cannot change.

That switch is only worth anything while three rules hold, and each of them is
one careless edit away from being untrue:

* a workflow that names a secret is not triggered by `pull_request`;
* no workflow hands a runner the pull request's head — under
  `pull_request_target` that would execute exactly the code the base-branch YAML
  exists to avoid, and `zrb_init.py` is loaded from the working directory, so a
  checkout is enough;
* every external action is pinned to a commit, because a tag is a moving pointer
  and `@v4` runs whatever it points at today.

The workflows under `.github/workflows` are the tree's CI, not part of the
package, so they are read as data here rather than imported.
"""

import re
from collections.abc import Callable
from pathlib import Path

WORKFLOWS = Path(__file__).parents[2] / ".github" / "workflows"

# The trigger, at the indentation a trigger sits at and with nothing after the
# word but the colon — which is what tells `pull_request:` from
# `pull_request_target:`.
_PULL_REQUEST_TRIGGER = re.compile(r"^ {2}pull_request:\s*$", re.MULTILINE)

_SECRET = re.compile(r"\bsecrets\.[A-Za-z_]")

# Reading the head as an event field is fine (`head.repo.full_name` is the fork
# check). Naming its commit or its branch is what puts contributor code on the
# runner: a `ref:` with one of these, or a `git checkout` built from one.
_HEAD_CHECKOUT = re.compile(
    r"github\.event\.pull_request\.(?:head\.(?:sha|ref)|merge_commit_sha)"
    r"|github\.head_ref"
)

_USES = re.compile(r"^\s*(?:-\s+)?uses:\s*(\S+)", re.MULTILINE)
_COMMIT = re.compile(r"[0-9a-f]{40}")


def _workflows() -> list[Path]:
    return sorted(WORKFLOWS.glob("*.yml"))


def _offenders(check: Callable[[str, str], str | None]) -> list[str]:
    """Each `file: detail` *check* reports over every workflow."""
    found: list[str] = []
    for path in _workflows():
        detail = check(path.name, path.read_text(encoding="utf-8"))
        if detail:
            found.append(detail)
    return found


def _pull_request_trigger_with_a_secret(name: str, text: str) -> str | None:
    if _SECRET.search(text) and _PULL_REQUEST_TRIGGER.search(text):
        return f"{name}: holds a secret and is triggered by pull_request"
    return None


def _head_checkout(name: str, text: str) -> str | None:
    match = _HEAD_CHECKOUT.search(text)
    if match:
        return f"{name}: {match.group(0)}"
    return None


def _unpinned_action(name: str, text: str) -> str | None:
    for match in _USES.finditer(text):
        uses = match.group(1)
        if uses.startswith("./") or uses.startswith("docker://"):
            continue
        reference = uses.rpartition("@")[2]
        if not _COMMIT.fullmatch(reference):
            return f"{name}: {uses}"
    return None


def test_a_workflow_holding_a_secret_is_not_triggered_by_pull_request():
    offenders = _offenders(_pull_request_trigger_with_a_secret)
    assert not offenders, (
        "A pull request can edit the workflow it runs, so a job holding a secret "
        "must be triggered by an event that resolves the base branch's YAML — "
        "`pull_request_target` rather than `pull_request`. Offenders: "
        + "; ".join(offenders)
    )


def test_no_workflow_checks_out_the_pull_request_head():
    offenders = _offenders(_head_checkout)
    assert not offenders, (
        "Read the pull request's head as a git object (git fetch, then a diff), "
        "never as a checkout: zrb loads zrb_init.py from the working directory. "
        "Offenders: " + "; ".join(offenders)
    )


def test_every_external_action_is_pinned_to_a_commit():
    offenders = _offenders(_unpinned_action)
    assert not offenders, (
        "Pin every external action to a full commit SHA, with the tag as a "
        "trailing comment. Offenders: " + "; ".join(offenders)
    )


def test_the_guards_read_a_planted_violation():
    """Each rule fails on the thing it is for, and only on that."""
    secret_and_pr = "on:\n  pull_request:\n    branches:\n      - main\n"
    secret = "    env:\n      KEY: ${{ secrets.OPENAI_API_KEY }}\n"
    target = "on:\n  pull_request_target:\n    branches:\n      - main\n"
    assert _pull_request_trigger_with_a_secret("w.yml", secret_and_pr + secret)
    assert not _pull_request_trigger_with_a_secret("w.yml", target + secret)
    assert not _pull_request_trigger_with_a_secret("w.yml", secret_and_pr)

    # The fork check reads the head's repository, which is data, not a checkout.
    fork_check = (
        "if: github.event.pull_request.head.repo.full_name == github.repository"
    )
    assert not _head_checkout("w.yml", fork_check)
    assert _head_checkout("w.yml", "ref: ${{ github.event.pull_request.head.sha }}")
    assert _head_checkout("w.yml", "ref: ${{ github.head_ref }}")
    assert _head_checkout("w.yml", "ref: ${{ github.event.pull_request.head.ref }}")

    assert not _unpinned_action(
        "w.yml", "uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4"
    )
    assert not _unpinned_action("w.yml", "uses: ./.github/workflows/_zrb.yml")
    assert _unpinned_action("w.yml", "uses: actions/checkout@v4")
