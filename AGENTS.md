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
- **Scoped writes:** use the underlying `ContextVar` (`token = var.set(...)` then `var.reset(token)`). Canonical pattern in `run_agent.py`.

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
