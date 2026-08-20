# Zrb Agent Guide

## Project Overview

Zrb (Zaruba) is a Python task automation framework (v2.x). Pure-Python task definitions, DAG-based execution, CLI and web UI runners, and built-in LLM/AI agent integration. Core in `src/zrb/`.

## Development Setup

```bash
source .venv/bin/activate && poetry lock && poetry install
```

Run tests: `source .venv/bin/activate && ./zrb-test.sh [path]` — pass nothing for all, or a file / directory / `file::test_function` path to scope.

## Where the code lives

`ls src/zrb/` plus each module's docstring is the authority; this is the orientation map.

| Path | What is in it |
| --- | --- |
| `attr/`, `env/`, `input/` | Deferred-evaluation attribute types, `Env`, `Input` |
| `builtin/` | Pre-packaged user-executable tasks (`zrb <group> <task>`) |
| `callback/`, `xcom/` | Task callbacks, and the per-task FIFO queue tasks exchange values through |
| `cmd/`, `content_transformer/` | Shell command building, `Scaffolder` content rewriting |
| `config/` | The `CFG` singleton, composed from mixins under `mixins/`. `CFG.FOO` access stays flat regardless of which mixin owns it |
| `context/`, `session/`, `session_state_log*/` | Three-tier context (SharedContext → Session → Context) and run state |
| `dot_dict/`, `util/` | `DotDict`, plus string/file/cmd/truncation helpers |
| `group/`, `task_status/` | CLI group tree, per-task status tracking |
| `llm/` | Everything LLM — see below |
| `llm_plugin/` | The built-in skills and agents that ship with zrb |
| `runner/` | `cli.py`, `web_app.py` + `web_route/`, and `chat/` (the chat session HTTP layer) |
| `task/` | The task engine: `BaseTask`, `Task`, `CmdTask`, `HttpCheck`, `TcpCheck`, `Scheduler`, `Scaffolder`, `RsyncTask`, and the `make_task` decorator |
| `contextvars.py` | Canonical index of every ambient `ContextVar`, its owning module, and its typed wrapper |

Inside `llm/`:

| Path | What is in it |
| --- | --- |
| `agent/` | Agent construction and the run loop. `run/runner.py` is the entry point; `subagent/` handles delegation; `gates.py` enforces permission denials |
| `app/`, `ui/` | The prompt_toolkit TUI (`app/`) and the UI protocol plus its implementations (`ui/`) |
| `approval/`, `permission/` | The approval channel, and the permission ruleset (`policy.py`, `state.py`) |
| `config/` | LLM-specific config: model resolution, the rate limiter |
| `custom_command/` | Slash commands built from skills and markdown |
| `history_manager/`, `summarizer/` | Conversation persistence and two-tier summarization |
| `hook/` | Claude-compatible lifecycle hooks |
| `lsp/`, `sandbox/`, `snapshot/`, `voice/` | Language-server clients, the opt-in FS sandbox, filesystem snapshots, voice dictation |
| `prompt/` | System-prompt composition — `manager.py`, `profile.py`, `live_context.py`, and the `markdown/` section files |
| `skill/` | Skill discovery and activation |
| `task/` | `llm_task.py` (`LLMTask`) and `task/chat/` (`LLMChatTask`) — both `BaseTask` subclasses that build pydantic-ai agents internally |
| `tool/` | Agent-callable tools, one module per tool family |
| `tool_call/` | Tool-call rendering, argument formatting, and tool policies |
| `common_tools.py` | Registers the shared baseline used by `LLMChatTask`, `LLMTask` and `SubAgentManager` |

`llm_plugin/` is split into core and optional content: `core_skills/` (always-on methodology baseline), `skills/` (utility skills, gated by `CFG.LLM_ENABLE_BUILTIN_SKILLS`), `core_agents/` (always-on sub-agents), and `agents/` (optional sub-agents, gated by `CFG.LLM_ENABLE_BUILTIN_AGENTS`). Each skill is `SKILL.md` or `SKILL.py`; each agent is `*.agent.md`. The toggles suppress only optional built-in content — user, project and plugin skills and agents always load (ADR-0054).

`test/` mirrors the `src/` hierarchy. The mirror is a *naming* rule, not a completeness claim: where a test exists it sits at the mirrored path, but many modules are covered through a caller instead.

> For a top-down tour of `zrb llm chat "..."` (CLI → task → agent run → UI → history), see `docs/advanced-topics/llm-chat-lifecycle.md`.

## LLM Prompt System

`PromptManager` (`llm/prompt/manager.py`) composes the system prompt from ordered sections; the default order and every knob are in `config/mixins/llm_prompt.py::DEFAULT_LLM_INCLUDE_SECTIONS`. Section wording lives in `llm/prompt/markdown/`; the `profile` section resolves as `profile.{name}.md` from the three profiles (`minimal`/`standard`/`capable`) plus the optional `auto` model-id ladder in `prompt/profile.py` (ADR-0049). Every design decision here — section order, where a rule lives, the profile ladder, the journal, tool-definition weight — is recorded in the ADRs. Read `docs/adr/README.md` (Prompt; Skills, agents and the journal; Tools and safety) before changing any of it.

The `markdown/` section files are the single source of truth for prompt wording — there is no generator, so edit them directly. Do not rewrap or trim them blindly: wording and composition invariants are documented in ADR-0049, and the public behavior (profile → section file, section filtering, file resolution) is pinned by tests.

## Ambient State (`ContextVar`s)

Canonical index in `src/zrb/contextvars.py` — every var, its owning module, and its typed wrapper.

- **Reading:** prefer the wrapper.
- **Scoped writes:** use the underlying `ContextVar` (`token = var.set(...)` then `var.reset(token)`). Canonical pattern in `agent/run/runner.py`.

## Worktree Storage

Git worktrees live at `{git_root}/.zrb/worktree/{branch_name}` (gitignored).

## Architecture Decision Records

Record a decision as an ADR in `docs/adr/` when it is **non-trivial** (a reasonable developer could pick a different path), **consequential** (affects other parts of the system or how users interact with it), and **persistent** (meant to last, not a quick hack). One decision per record.

**When a decision changes, rewrite the record that owns it** rather than adding a "supersedes ADR-NNNN" record — the log describes the system as it stands, and the chronology lives in git and the changelog. Mechanics and the record shape are in [`docs/adr/README.md`](docs/adr/README.md).

## Changelog

Lives under `docs/`: `changelog.md` (index), `changelog-v2/` (per-minor files, e.g. `2.54.0.md`, `2.50.0-2.50.9.md`), `changelog-v1.md` (1.x archive). Entry format and the compaction procedure are in [Maintainer Guide → Changelog](docs/advanced-topics/maintainer-guide.md#changelog).

## Development Conventions

### Code Style

- Follow existing project conventions (formatting, naming, typing).
- **Modularity:** prefer functions under ~30 lines; helpers placed below their callers. This is a target for *new* code, not a repo-wide invariant — several hundred existing functions exceed it (keybinding tables, hook creators, constructors). Going long is fine when splitting would only scatter a single linear procedure; don't split to hit the number, and don't cite the number as if it were enforced.
- **`Mixin` means reusable** (ADR-0035). Suffix a class `Mixin` only when it reads no state it does not itself set, so any class can mix it in (`BufferedOutputMixin` in `ui/buffered_output.py`; most of the `CFG` mixins under `config/mixins/`). A class that reads attributes only one host provides is a *part* of that host — but a part is **composed, not inherited**: the owner instantiates it and holds it as a named attribute (`self._building = LLMTaskBuilding(self)`), keeping only a normal single-inheritance base (`BaseTask`, `BaseUI`, ...) where that is a genuine is-a relationship. Name a part `<Owner><Aspect>` in a file named for the aspect — `ChatExecution` in `task/chat/execution.py`, `BaseUICommands` in `ui/base/commands.py`. No `_mixin` suffix, no leading underscore (these are imported across modules, so "module-private" would be a false claim).
  - **How a part reaches what it needs** is chosen per part: pure data with no cross-part calls is passed directly as constructor/method arguments; needing one specific sibling's behavior means holding a reference to that already-constructed sibling; needing behavior spread across several siblings *or* the owner's own methods, or state reachable through a public setter the owner may reassign later, means holding a reference to the **owner** and reaching its state **only through a public property or method** (`self._owner.x`) — never the raw underscored attribute (`self._owner._x`). If the owner has no public accessor for that piece of state yet, add one; that one-line cost is the whole point, not a shortcut to skip. `TYPE_CHECKING` host-contract blocks are gone — a part's constructor parameter is typed as the real owner/sibling class, so the type checker verifies accesses directly.
  - **The owner re-exposes every part method/property as a one-line delegator** (`def append_tool(self, *t): self._building.append_tool(*t)`), so external call sites keep working unchanged. **This pattern is PROHIBITED: `self._a_property._a_method_of_the_property()` / `self._a_property._a_subproperty`** — a delegator or a part reaching a sibling/owner never crosses a `_`-prefixed name; if the thing on the other side needs exposing, expose it (rename to public, or add a new public accessor) rather than reaching around it. This applies in production code and in tests alike: in tests, cross-object private access should be zero.
  - **A method the host calls by name, a sibling part declares, or a subclass overrides is public too** — `LLMTaskHistory.get_conversation_name`, `LLMTaskBuilding.get_model`. Only helpers called from inside their own part keep the underscore — a name is private only when nothing outside that one class (no owner, no sibling, no test) ever names it. See ADR-0035.
- **No path stutter.** `X/manager/manager.py` is `X/manager.py`; siblings become `X/manager_<aspect>.py`. **The 18 `X/X.py` paths are not this** — `task/task.py`, `group/group.py`, `config/config.py` and the rest are `<package>/<eponymous-type>.py`, a package named for its principal type. Every one of those names is a top-level `zrb` export with deep-import users, and `task/task.py` cannot become `task.py` without colliding with the `task/` package.
- **One verb per collection operation.** Ordered pipelines take **`append_X`** and **`prepend_X`**; unordered registries take **`add_X`** (`skill_manager.add_skill`, `sub_agent_manager.add_agent`, `Group.add_task`). An ordered collection has no `add_X` alias: position is the whole semantics of those calls, so the name states it — `add_` on an ordered collection cannot say whether it inserts at the front or the back, and both readings are in use across such APIs.
- **Error handling:** an LLM tool error the *model* has to recover from carries a `[SYSTEM SUGGESTION]` prefix with actionable guidance (ADR-0057). Ordinary programmer errors (bad argument, broken invariant) stay plain `ValueError`/`RuntimeError` — the prefix is for text the model reads, not for every raise.

### Config Conventions

Boolean `CFG`/env knobs follow a naming rule (ADR-0026):

- **`<NAMESPACE>_ENABLED`** (state-last) when the toggle is the master switch of a namespace that has *other* settings, so it groups with its siblings — `WEB_AUTH_ENABLED` (alongside `WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES`), `LLM_SANDBOX_ENABLED`, `HOOKS_ENABLED`, `LLM_JOURNAL_ENABLED`.
- **Verb-first** (`ENABLE_`/`SHOW_`/`SEARCH_`/`INCLUDE_`/`ALLOW_`) for a standalone on/off behavior with no sub-config namespace — `LLM_ENABLE_BUILTIN_SKILLS`, `LLM_SEARCH_PROJECT`, `LLM_SHOW_TOOL_CALL_DETAIL`.

When **renaming** a released knob, preserve the old env key via `EnvField(aliases=[new, old], write_key=new)` (reads either, writes the new form). A clean break is only safe pre-release.

### Imports

Default to module-level imports. An in-function import must justify itself with a `# lazy: <reason>` comment matching one of:

1. **Heavy third-party deferral** — `pydantic_ai`, `prompt_toolkit`, `mcp`, `fastapi`, `boto3`, `anthropic`, `openai`, `chromadb`, `playwright`, and other extras-marked packages.
2. **Transitively heavy via internal** — an internal `zrb.*` module that eagerly imports a heavy package inherits the rule. Hoisting silently re-introduces the slow load.
3. **Circular import** — name the cycle: `# lazy: circular — tool → ui → llm_task → here`.
4. **Test patch seam** — tests patch at the source path and rely on the patch taking effect inside a consumer; hoisting binds the name at consumer-load time and bypasses the mock. Tag: `# lazy: tests patch <path>; hoisting bypasses the mock`.

`# noqa: F401` belongs only on imports that exist as a test-patch attribute on the module itself — verify the patch targets working code; a patch against a name nothing reads should be deleted, not preserved.

`flake8 src/zrb --select=F` runs as part of `./zrb-test.sh` and fails on unused or duplicate imports.

### Test Guidelines

**Principles** (ADR-0034):

- **Coverage:** ≥ 90%
- **Public API only.** NEVER access or test private members (anything `_prefix`). If internal behavior is hard to test publicly, refactor the class to expose a public hook or property.
  - The usual seam for a private helper is **the public entry point plus the boundary the helper's effect crosses** — drive the public function, then assert on what reached the mocked dependency. `test/llm/tool/test_code.py` does this: `analyze_code` is the entry point, `run_agent` is the boundary, and patching `CFG` steers the thresholds, so the private helpers' behavior is verified without naming either.
  - Mocking a *public* dependency the module imported (`run_agent`, `llm_limiter`) is not a private-member access; mocking `_private_helper` is.
- Use `pytest` fixtures and mocks for external dependencies.
- Follow Arrange-Act-Assert (AAA).

**Test file conventions:**

- ❌ No suffixes like `_advanced.py`, `_coverage.py`, `_extra.py`, `_comprehensive.py`
- ✅ Single source of truth: update the main test file (`test_manager.py`), not a sibling
- ✅ Split files >500 lines by **feature group** (`test_manager_lifecycle.py`, `test_manager_search.py`), not by depth or coverage level
- ⚠️ Mirroring `src/` produces **duplicate basenames** (`test_manager.py` under `hook/`, `lsp/`, `snapshot/`, …). pytest imports rootdir-relative, so two bare `test_manager.py` files collide at collection. Fix by adding an empty `__init__.py` to the test directory. Keep the mirrored filename; do not rename the test to dodge the clash.

**Coverage exclusions** (`.coveragerc`) — do not test these directly:

- `any_*.py` — protocols / interfaces (no implementation)
- `__main__.py` — entry points (tested via integration)
- `__init__.py` — re-exports only
- `zrb_init.py` — user-defined initialization, not library code
