# Zrb Agent Guide

## Project Overview
Zrb (Zaruba) is a Python task automation framework (v2.x). Pure-Python task definitions, DAG-based execution, CLI and web UI runners, and built-in LLM/AI agent integration. Core in `src/zrb/`.

## Development Setup
```bash
source .venv/bin/activate && poetry lock && poetry install
```

## Project Structure

The tree is self-describing — `ls src/zrb/` plus each module's docstring covers the rest. Worth knowing up front:

- `src/zrb/builtin/` — pre-packaged user-executable tasks (`zrb <group> <task>`)
- `src/zrb/config/` — `CFG` singleton, composed from mixins under `_mixins/`. **`CFG.FOO` access stays flat** regardless of which mixin owns the attribute.
- `src/zrb/task/` — task engine: `BaseTask`, `Task`, `CmdTask`, `HttpCheck`, `TcpCheck`, `Scheduler` (extends `BaseTrigger`), `Scaffolder`, `RsyncTask`. Plus the `make_task` decorator (wraps a plain function into a `BaseTask`).
- `src/zrb/llm/` — LLM integration. `task/llm_task.py` (`LLMTask`) and `task/chat/task.py` (`LLMChatTask`) are `BaseTask` subclasses that create pydantic-ai agents internally. `prompt/` composes the system prompt; `tool/` ships agent-callable tools; `agent/subagent/` handles delegation; `common_tools.py` registers the shared baseline used by `LLMChatTask`, `LLMTask`, and `SubAgentManager`.
- `src/zrb/llm_plugin/` — built-in skills (`skills/`) and sub-agent definitions (`agents/`). Each skill is `SKILL.md` or `SKILL.py`; each agent is `*.agent.md`.
- `test/` — mirrors `src/` hierarchy
- `llm-challenges/runner.py` — agent framework evaluation

> For a top-down tour of `zrb llm chat "..."` (CLI → task → agent run → UI → history), see `docs/advanced-topics/llm-chat-lifecycle.md`.

## LLM Prompt System

`PromptManager` (`src/zrb/llm/prompt/manager.py`) assembles the system prompt from ordered sections. Default order in `config/mixins/llm_prompt.py::DEFAULT_LLM_INCLUDE_SECTIONS`:

`persona → mandate → git_mandate → journal_mandate → system_context → project_context → tool_guidance → claude_skills`

User-added prompts follow. Override via the `include_sections` constructor parameter or the `ZRB_LLM_INCLUDE_SECTIONS` env var (comma-separated, order-sensitive).

A section name that is **not** a built-in resolves as a custom, config-positioned section (precedence: built-in > registered provider > markdown file):
- **Registered provider** — `prompt_manager.register_section("company_context", lambda ctx: ...)` registers a dynamic provider, composed by calling it with the active context at compose time. Use for always-on content that reflects runtime state (current sprint, deploy target, live schema). Return `""` to emit nothing.
- **Markdown file** — otherwise the name resolves via `get_prompt(name)` (project-override → env → base-prompt-dir → package), so `company_context` loads `company_context.md` with the usual `{PLACEHOLDER}` substitution. Missing files resolve to `""` (harmless no-op; a warning is logged at compose time so an unknown/misspelled name is diagnosable).

Either way, downstreams add ordered sections without editing `PromptManager`. See ADR-0061.

**Each section is MECE — a single behavior lives in exactly one section.** Adding a rule: pick the smallest-scope section that owns the concept.

- `persona` — identity + response style
- `mandate` — operating rules (no tool/git specifics)
- `git_mandate` — git approval rules
- `journal_mandate` — memory protocol + index
- `system_context` — runtime facts; auto-injects session wiring, active worktree, and pending todos so todo tools target the right conversation and stale state self-clears
- `project_context` — AGENTS.md / CLAUDE.md project overrides
- `tool_guidance` — per-tool when-to-use + key rules
- `claude_skills` — skill catalogue

### Ambient State (`ContextVar`s)

Canonical index in `src/zrb/contextvars.py` — every var, its owning module, and its typed wrapper.

- **Reading:** prefer the wrapper.
- **Scoped writes:** use the underlying `ContextVar` (`token = var.set(...)` then `var.reset(token)`). Canonical pattern in `agent/run/runner.py`.

### Worktree Storage

Git worktrees live at `{git_root}/.zrb/worktree/{branch_name}` (gitignored).

### Configuring Tool Guidance

Tool guidance is fully explicit — no static catalogue. Register via:

```python
prompt_manager.add_tool_guidance(group="My Tools", name="MyTool",
    use_when="Doing X when Y", key_rule="Pass --flag; never call without context.")
```

`add_tool_group` is called automatically when the group does not yet exist.

`LLMChatTask._exec_action` sets `prompt_manager.tool_names` from the resolved tool list at runtime; guidance for unregistered tools is suppressed. **For factory-created tools whose Python function names differ from their LLM-visible names**, register an `add_tool_guidance()` entry explicitly — otherwise the runtime-name filter drops them.

## Architecture Decision Records (ADRs)

Significant design decisions are recorded as ADRs in `docs/adr/`. Each ADR
captures context, decision, consequences, alternatives rejected, and evidence
(cross-references to code/docs). The index at `docs/adr/README.md` lists every
record.

### When to write one

Write an ADR when a decision is:
- **Non-trivial** — a reasonable developer could pick a different path.
- **Consequential** — affects how other parts of the system work or how users
  interact with it.
- **Persistent** — the decision is expected to last (not a quick hack).

### How to add one

1. Find the next free `ADR-NNNN` in the index.
2. Append to the relevant thematic file under `docs/adr/`.
3. Add a row to the index in `docs/adr/README.md`.
4. If the decision reverses or refines an old ADR, mark the old one
   `Superseded by ADR-NNNN` — preserve the history.

### Format

Every ADR uses this shape:

- **Status** — Accepted / Superseded / Evolving
- **Context** — the forces and problem that prompted the decision
- **Decision** — what was chosen, concretely
- **Consequences** — what this buys and what it costs
- **Alternatives rejected** — and why
- **Evidence** — file/doc pointers; tag each rationale `[DOCUMENTED]` (stated
  in code/docs) or `[INFERRED]` (deduced from code structure)

One decision per record. If the decision is still being discussed, mark it
**Evolving** and note open questions as `@<owner> please decide` tags.

## Changelog

Three files under `docs/`, newest-first within each:

- `changelog.md` — the **active** changelog: recent releases at full detail.
- `changelog-v2.md` — archive of the 2.x line.
- `changelog-v1.md` — archive of the 1.x line (and the 1.0.0 rewrite from 0.x).

### Entry format

Each release is a `## <version> (<Month D, YYYY>)` heading followed by themed
bullets. One blank line between entries. Use `- **<Category>: <Title>**:` with
nested `  - <detail>` sub-bullets; categories are free-form but conventionally
`Feature` / `Improvement` / `Fix` / `Reliability` / `Security` / `Refactor` /
`Performance` / `Chore` / `Documentation` / `Tests`. Write past-tense and
factual, and reference concrete symbols/paths (`module.py`, `ClassName`, env
vars, ADR-NNNN) so a reader can locate the change.

### Collapsing (compaction)

Old entries are periodically compacted so each minor keeps only two entries —
the minor bump and its final revision — giving the retained sequence:

```
x.y.0  →  x.y.z (latest revision of x.y)  →  x.y+1.0  →  …
```

The kept `x.y.z` **summarizes** the dropped patches `x.y.1`–`x.y.z`, and `x.y.0`
**absorbs** its pre-releases (`x.y.0a*`/`x.y.0b*`) — never just dropped, since
the real features usually live there. Rolled-up entries get a
`_Cumulative summary of the X.Y.1–X.Y.Z patch line._` note. The newest minor in
`changelog.md` stays at full per-patch detail until it ages out.

Full procedure, rationale, and a worked example:
[Maintainer Guide → Changelog](docs/advanced-topics/maintainer-guide.md#changelog).

## Development Conventions

### Code Style
- Follow existing project conventions (formatting, naming, typing)
- **Modularity:** functions ~30–50 lines; helpers placed below their callers
- **Error handling:** LLM tool errors include a `[SYSTEM SUGGESTION]` prefix with actionable guidance

### Imports

Default to module-level imports. An in-function import must justify itself with a `# lazy: <reason>` comment matching one of:

1. **Heavy third-party deferral** — `pydantic_ai`, `prompt_toolkit`, `mcp`, `fastapi`, `boto3`, `anthropic`, `openai`, `chromadb`, `playwright`, and other extras-marked packages. Slow to import, not needed on every code path.
2. **Transitively heavy via internal** — an internal `zrb.*` module that eagerly imports a heavy third-party package inherits the rule. Hoisting silently re-introduces the slow load.
3. **Circular import** — name the cycle: `# lazy: circular — tool → ui → llm_task → here`.
4. **Test patch seam** — tests sometimes patch at the source path and rely on the patch taking effect inside a consumer. Hoisting binds the name at consumer-load time and bypasses the mock. Tag: `# lazy: tests patch <path>; hoisting bypasses the mock`.

`# noqa: F401` belongs only on imports that exist as a test-patch attribute on the module itself — verify the patch actually targets working code; cargo-cult patches against names nothing reads should be deleted, not preserved.

`flake8 src/zrb --select=F` runs as part of `./zrb-test.sh` and fails on unused or duplicate imports.

### Test Guidelines

Run: `source .venv/bin/activate && ./zrb-test.sh [path]` — pass nothing for all, or a file / directory / `file::test_function` path to scope.

**Principles:**
- **Coverage:** ≥ 90%
- **Public API only.** NEVER access or test private members (anything `_prefix`). If internal behavior is hard to test publicly, refactor the class to expose a public hook or property.
- Use `pytest` fixtures and mocks for external dependencies
- Follow Arrange-Act-Assert (AAA)

**Test file conventions:**
- ❌ No suffixes like `_advanced.py`, `_coverage.py`, `_extra.py`, `_comprehensive.py`
- ✅ Single source of truth: update the main test file (`test_manager.py`), not a sibling
- ✅ Split files >500 lines by **feature group** (`test_manager_lifecycle.py`, `test_manager_search.py`), not by depth or coverage level

**Coverage exclusions** (`.coveragerc`) — do not test these directly:
- `any_*.py` — protocols / interfaces (no implementation)
- `__main__.py` — entry points (tested via integration)
- `__init__.py` — re-exports only
- `zrb_init.py` — user-defined initialization, not library code
