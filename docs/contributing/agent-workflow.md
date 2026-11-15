🔖 [Documentation Home](../README.md) > [Contributing](./) > Agent Workflow

# Agent Workflow

How an agent turns a request into a reviewed, green pull request. A human contributor follows the same path, with the vocabulary of [Maintainer Guide → Submitting a Change](maintainer-guide.md#submitting-a-change); this page adds what a parallel, tool-driven worker needs to get right.

## Environment

Activate the virtual environment before any test, lint or code run, in every shell. A command that runs without it is testing a different installation:

```bash
source .venv/bin/activate
```

First time only: `python -m venv .venv && poetry install`. Run `poetry lock` only after editing dependencies. `./zrb-test.sh` is the gate; `./zrb-test.sh ratchet` is the fast architecture loop; a scoped run is a working loop, never the gate.

## Branches and worktrees

- One logical change per branch, based on `origin/main`. Do not stack unrelated work on a branch that is under review.
- Branch names: `feat/<short-name>`, `fix/<short-name>`, `docs/<short-name>`, `refactor/<short-name>`, `chore/<short-name>`. The name says what the change is, not the ticket number.
- Prefer a separate [git worktree](https://git-scm.com/docs/git-worktree) per branch so several changes run in parallel without moving the main checkout. They live under `.zrb/worktree/`, which is gitignored:

```bash
git fetch origin
git worktree add .zrb/worktree/<branch> -b <branch> origin/main
```

- Remove the worktree once its pull request is merged: `git worktree remove .zrb/worktree/<branch>`.
- Never push to `main`, force-push a shared branch, or merge a pull request unless you were asked to.

## While working

- Read the owner first: the module, its test, the architecture page and the ADR. The change should look like the code already there.
- Keep the diff scoped. An unrelated cleanup is a separate branch, not a stowaway commit.
- Do not bump `pyproject.toml`'s version; that is a maintainer-only commit tied to publishing.
- Update the docs, examples and changelog-or-ADR the change invalidates in the same diff. A doc that names a moved file fails the suite.

## Commit and push

- Imperative subject, no prefix: `Ask the judge for a shape`, not `feat: judge`. The body states what was wrong, what changed and why, in prose paragraphs, and ends with the verification:

```text
Verified: ./zrb-test.sh — 11256 passed, 48 skipped, 96.03%, exit 0.
flake8 src/zrb --select=F clean, pyright src/zrb 0 errors.
```

- One logical change per commit. Do not add generated files, `.venv`, or a worktree path.
- Run the full `./zrb-test.sh` before pushing. A scoped run proves the tests you touched; the gate proves the tree.
- Push the branch: `git push -u origin <branch>`.

## Pull request

Open the pull request against `main` and follow [`.github/pull_request_template.md`](../../.github/pull_request_template.md):

- **Summary** — what changed and why, for a reviewer who has not read the diff. Add an **Evidence** block with the commands run and their result.
- **Checklist** — license, ready for review, changelog entry (or N/A with a reason), ADR (or N/A with a reason).
- **Ticket or Issue** — the issue number when there is one.
- **How to Test** — the exact commands, or the scenario a person can follow.

The title is the commit subject: one sentence, no `feat:`/`fix:` prefix. Recent merged pull requests are the model for tone and structure.

## Review, then green

1. Open the pull request. The [Code Review](../../.github/workflows/code-review.yml) workflow posts a review comment; the test matrix starts beside it.
2. **Wait for the review before calling the change ready.** Read every finding.
3. Fix what is right and answer what is not, in one reply per finding. Push the fixes to the same branch; the review and the checks run again.
4. Once the review has landed with LGTM and no open issue, **wait for every check**:

```bash
gh pr checks <number> --watch
```

5. Report the outcome: the pull request URL, what changed, the evidence (test result), the review verdict and the final check status.

A pull request with a red check or an unanswered finding is not done, even when the code is correct. Merge only when the request asked for a merge; otherwise hand the green pull request back with the report.

---

🔖 [Documentation Home](../README.md) > [Contributing](./) > Agent Workflow
