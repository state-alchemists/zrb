# Zrb Agent Guide

Zrb (Zaruba) is a Python coding agent with a built-in task DAG (v3.x): an LLM agent (`zrb llm chat`), pure-Python task definitions, a DAG executor, and CLI and web UI runners. Core in `src/zrb/`.

This file is the entry point, not the manual. It lists what every change must satisfy and points to the page that owns the detail. Read that page — and the module and test it names — before changing the area.

## Read first

| I am… | Read |
| --- | --- |
| Setting up, running tests, changelog, release | [Maintainer Guide](docs/contributing/maintainer-guide.md) |
| Adding code and unsure which pattern fits | [Which pattern do I reach for?](docs/contributing/which-pattern.md) |
| Writing code: style, naming, imports, tests | [Coding Conventions](docs/contributing/coding-conventions.md) |
| Looking for a file | [Code Map](docs/contributing/code-map.md); `ls src/zrb/` and module docstrings are the authority |
| Checking what a test enforces | [Framework Conventions (R1–R13)](docs/contributing/framework-conventions.md) |
| Understanding a subsystem | [Architecture](docs/architecture/README.md) |
| Asking why something is the way it is | [ADRs](docs/adr/README.md) |
| Branch, commit, PR, review, CI | [Agent Workflow](docs/contributing/agent-workflow.md) |

## Every change must satisfy

1. **Look like the code around it.** One person wrote this tree: read the neighbours, its test and the owning doc, and match the naming, error style, layering and test layout. Extend an existing module before inventing a new one. → [The shape of the code](docs/contributing/coding-conventions.md#the-shape-of-the-code)
2. **High cohesion, low coupling, SOLID.** One job per module and class; depend on `Any*` contracts and L0 facades, not on concrete higher layers; reach another object only through its public surface. → [SOLID in this tree](docs/contributing/coding-conventions.md#solid-in-this-tree)
3. **Do not break the public API.** `zrb.__all__`, exported members and constructor parameters are pinned by a snapshot. Prefer an additive change; a necessary break is announced in the PR and changelog, and the snapshot is regenerated in the same diff. → [Public API](docs/contributing/coding-conventions.md#public-api)
4. **Name by A/HC/LC and S-I-D.** `prefix? + action + high context + low context?`; short, intuitive, descriptive; booleans read as questions; one verb per meaning. → [Naming](docs/contributing/coding-conventions.md#naming)
5. **Load heavy dependencies lazily.** Module-level imports are the default; an in-function import states one of the five accepted reasons with `# lazy: <reason>`. → [Imports and lazy loading](docs/contributing/coding-conventions.md#imports-and-lazy-loading)
6. **Activate `.venv` before any test or code run.** `source .venv/bin/activate`, then `./zrb-test.sh [path]`. → [Environment](docs/contributing/agent-workflow.md#environment)
7. **Work in parallel with worktrees and branches.** One logical change per branch and worktree, based on `origin/main`, under `.zrb/worktree/`. → [Branches and worktrees](docs/contributing/agent-workflow.md#branches-and-worktrees)
8. **Keep the graph acyclic and the layout boring.** Lower layers never import higher ones; a new `# lazy: circular` means a misplaced module, not a comment. No path stutter; the test tree mirrors `src/`. → [Layout and dependencies](docs/contributing/coding-conventions.md#layout-and-dependencies)
9. **Ship the docs with the code.** Update the page, example, changelog entry or ADR the change invalidates in the same PR. A doc that names a moved file fails the suite. → [Documentation does not lag](docs/contributing/coding-conventions.md#documentation-does-not-lag)
10. **Follow the PR protocol.** Open a PR from the template, wait for the review, fix or answer every finding, then wait for every check green before calling the work done. → [Review, then green](docs/contributing/agent-workflow.md#review-then-green)

## Commands

```bash
source .venv/bin/activate
./zrb-test.sh ratchet   # architecture and doc guards only (~90s)
./zrb-test.sh [path]    # one file, directory or file::test
./zrb-test.sh           # full gate: flake8, pyright, pytest, coverage ≥ 95%
```

## References

- Architecture overview and reading paths: [docs/architecture/README.md](docs/architecture/README.md)
- LLM layering quick map: [docs/llm/quick-map.md](docs/llm/quick-map.md)
- ADR index: [docs/adr/README.md](docs/adr/README.md)
- Contributing index: [docs/contributing/README.md](docs/contributing/README.md)
