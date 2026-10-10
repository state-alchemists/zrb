# Zrb Agent Guide

## Project Overview

Zrb (Zaruba) is a Python coding agent with a built-in task DAG (v3.x). An LLM agent (`zrb llm chat`) plus pure-Python task definitions, DAG-based execution, and CLI and web UI runners. Core in `src/zrb/`.

## Development Setup

See [Maintainer Guide → Getting Started](docs/contributing/maintainer-guide.md#getting-started) for environment setup, running tests, and troubleshooting a failing `zrb-test.sh`.

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
| `task/` | The task engine: `BaseTask`, `Task`, `CmdTask`, `HttpCheck`, `TcpCheck`, `Scheduler`, `Scaffolder`, `RsyncTask`, and the `make_task` decorator. Shared constructor keywords live once in `base/params.py` |
| `contextvars.py` | Canonical index of every ambient `ContextVar`, its owning module, and its typed wrapper |

Inside `llm/`:

| Path | What is in it |
| --- | --- |
| `agent/` | Agent construction and the run loop. `run/runner.py` is the entry point; `subagent/` handles delegation; `gates.py` enforces permission denials |
| `ui/` | The UI protocol (`any_ui.py`) plus its implementations; the prompt_toolkit TUI lives under `ui/default/app/` |
| `approval/`, `permission/` | The approval channel, and the permission ruleset (`policy.py`, `state.py`) |
| `config/` | LLM-specific config: model resolution, the rate limiter |
| `custom_command/` | Slash commands built from skills and markdown |
| `history_manager/`, `summarizer/` | Conversation persistence and two-tier summarization |
| `hook/` | Claude-compatible lifecycle hooks |
| `lsp/`, `sandbox/`, `snapshot/` | Language-server clients, the opt-in FS sandbox, filesystem snapshots |
| `camera/`, `dictation/`, `speech/` | Optional chat features — `/photo`, speech-to-text input, replies read aloud. Each is one `enable_*` call plus a config dataclass and a `backend/` package, and none is known to the UI (ADR-0102) |
| `voice/` | The Pipecat STT/TTS service registry that `dictation/` and `speech/` select their backend from |
| `prompt/` | System-prompt composition — `manager.py`, `profile.py`, `live_context.py`, and the `markdown/` section files |
| `skill/` | Skill discovery and activation |
| `task/` | `llm_task.py` (`LLMTask`) and `task/chat/` (`LLMChatTask`) — both `BaseTask` subclasses that build pydantic-ai agents internally |
| `tool/` | Agent-callable tools, one module per tool family |
| `tool_call/` | Tool-call rendering, argument formatting, and tool policies |
| `util/` | LLM-side helpers: streaming, PDF/clipboard capture, history formatting, model capabilities |
| `message.py`, `factory_resolver.py`, `input_source.py`, `stream_observer.py` | Message-history repair (role alternation, orphaned tool calls), merging static and factory-produced tools, user-turn provenance, and the outside-the-UI stream observers (`enable_speech` uses one) |
| `common_tools.py` | Registers the shared baseline used by `LLMChatTask`, `LLMTask` and `SubAgentManager` |
| `agent_state.py`, `agent_tool_result.py` | Leaf modules `zrb.llm.agent` depends on, kept at top level so importing them does not trigger `agent/`'s package `__init__` (ADR-0088) |

`llm_plugin/` is split into core and optional content: `core_skills/` (always-on methodology baseline), `skills/` (utility skills, gated by `CFG.LLM_ENABLE_BUILTIN_SKILLS`), `core_agents/` (always-on sub-agents), and `agents/` (optional sub-agents, gated by `CFG.LLM_ENABLE_BUILTIN_AGENTS`). Each skill is `SKILL.md` or `SKILL.py`; each agent is `*.agent.md`. The toggles suppress only optional built-in content — user, project and plugin skills and agents always load (ADR-0054).

`test/` mirrors the `src/` hierarchy. The mirror is a *naming* rule, not a completeness claim: where a test exists it sits at the mirrored path, but many modules are covered through a caller instead.

**Two registration steps that are easy to forget. Both now fail as test failures rather than silently:**
- A new task under `builtin/` must also be imported in `builtin/__init__.py` and added to its `__all__`, or it simply never appears in the CLI. Guarded by `test/builtin/test_registration_completeness.py` — including the tree scan for a module `__init__.py` never imports. A task that exists only as another task's `upstream=` dependency belongs in that file's `INTERNAL_TASKS` map, with its reason.
- A new tool under `llm/tool/` must also be registered *and* `tag()`-ed with a `Capability` in `llm/common_tools.py::_seed_default_tools`, or it resolves to `Capability.UNKNOWN` (denied in plan mode). Guarded by `test_every_registered_tool_carries_a_known_capability` in `test/llm/test_common_tools.py`. Leaving a *third-party* or MCP tool untagged is still fine — `UNKNOWN` is deliberately safe-by-default there.

`hook/manager.py` builds a `HookType.AGENT` hook through a registration seam (`hook/agent_hook_registry.py`), because `zrb.llm.agent` itself depends on `hook.manager`. The real builder (`agent/hook_agent.py`) registers when any name re-exported by `zrb.llm.agent` is first resolved (ADR-0096); if it is missing, the hook fails with a logged warning instead of crashing.

> For the design of each subsystem, see [`docs/architecture/README.md`](docs/architecture/README.md); for a top-down code tour of `zrb llm chat "..."` (CLI → task → agent run → UI → history), see `docs/llm/llm-chat-lifecycle.md`.

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

Lives under `docs/changelog/`: `README.md` (index), `v1.md` (1.x archive), `v2/` (per-minor files for the 2.x line, e.g. `2.54.0.md`, `2.50.0-2.50.9.md`), `v3/` (per-minor files for the 3.x line). Entry format and the compaction procedure are in [Maintainer Guide → Changelog](docs/contributing/maintainer-guide.md#changelog).

## Development Conventions

> New here? Start at the [Contributing guide](docs/contributing/README.md), then [Which pattern do I reach for?](docs/contributing/which-pattern.md).
> The enforced rule list is [Framework Conventions](docs/contributing/framework-conventions.md) (R1–R12). Cite rule numbers in review.

### Code Style

- Follow existing project conventions (formatting, naming, typing).
- **Modularity:** aim for functions under ~30 lines, helpers placed below their callers. A target for *new* code, not an enforced invariant — several hundred existing functions exceed it; don't split a single linear procedure just to hit the number.
- **`Mixin` means reusable; everything else is a composed part** (ADR-0035). The full rules are in [Which pattern → Mixin vs. part](docs/contributing/which-pattern.md#the-one-hard-call-mixin-vs-part); the short form:
  - Suffix a class `Mixin` only when it reads no state it does not itself set (`BufferedOutputMixin`, the `CFG` mixins under `config/mixins/`).
  - A class that reads state only one host provides is a *part*: the owner composes it (`self._building = LLMTaskBuilding(self)`), never inherits it. Name it `<Owner><Aspect>` in a file named for the aspect (`ChatExecution` in `task/chat/execution.py`) — no `_mixin` suffix, no leading underscore on the class.
  - A part reaches its owner or siblings **only through public properties or methods**; add the accessor if it is missing. **PROHIBITED: crossing a `_` name on another object** (`self._owner._x`, `self._a_property._a_method()`), in production code and in tests alike.
  - A part outside code needs is a **public attribute** (`ui.usage.session_token_usage`), not a wall of forwarders; inside the owner, call `self._part.method()` directly. A one-line delegator is only for a name the owner's contract declares (an `AnyUI` method, a documented hook like `BaseUI.accumulate_usage`).
  - A method the owner, a sibling, a subclass or a test names is public (`LLMTaskBuilding.get_model`).
  - On a class users subclass (`BaseTask`, `BaseUI`), an owner-only part is stored as `self._base_<aspect>` so a subclass's own `self._<aspect>` cannot silently overwrite it.
- **No path stutter.** `X/manager/manager.py` is `X/manager.py`; siblings become `X/manager_<aspect>.py`. **The 17 `X/X.py` paths are not this** — `task/task.py`, `group/group.py`, `config/config.py` and the rest are `<package>/<eponymous-type>.py`, a package named for its principal type. Flattening one would collide with its own package (`task/task.py` → `task.py` next to `task/`), and most of them (`Task`, `Group`, `Session`, `Xcom`, ...) are top-level `zrb` exports with deep-import users.
- **Collection verbs** ([R5/R6](docs/contributing/framework-conventions.md)). Ordered collections (prompts, tools, policies, UIs) take `append_X`, `prepend_X`, `set_X`, `remove_X` — never `add_X`, which cannot say front or back. Name- or event-keyed collections (skills, agents, hooks) take `add_X`, `set_X`, `remove_X` — never `append_X`.
- **One verb per meaning** (ADR-0098). The other 4,510 functions, which currently answer to 490 distinct leading tokens, 39.6% of them used once, converge on: `get_X` returns X (not `fetch`/`retrieve`/`lookup`); `resolve_X` evaluates a deferred attribute against a context (ADR-0005); `read_X` touches the filesystem, `load_X` imports or deserializes; `create_X` constructs (not `build`/`make`/`new`/`generate`); `remove_X` takes X out of a collection, `delete_X` destroys it at its source; `set_X`/`reset_X` assign and restore; `handle_X` processes an event; `enable_X` switches an optional feature on for a task (ADR-0102). A verb outside the list needs a reason. Review vocabulary only — no fitness test.
- **A function annotated `-> bool` is named as a question** — `is_`, `has_`, `should_`, `can_`, `needs_`, or an `_enabled`/`_active` property suffix (ADR-0098). Ratcheted by `test/architecture/test_bool_naming_ratchet.py`: the count of non-question names may only go down. Rename when touching a file for another reason, never as a sweep.
- **Error handling** ([R10](docs/contributing/framework-conventions.md), ADR-0057). An LLM tool error the *model* must recover from carries a `[SYSTEM SUGGESTION]` prefix with actionable guidance; ordinary programmer errors stay plain `ValueError`/`RuntimeError`. Catch only what the code can recover from: a non-re-raising `except Exception:` and `Any` in an annotation are both ratcheted (`test_broad_except_ratchet.py`, `test_any_annotation_ratchet.py`) and may only go down.

### Task Constructors

A task subclass spells out only the keywords it adds and takes its parent's as
`**kwargs: Unpack[BaseTaskParams]` (`task/base/params.py`). Call sites are
unaffected — `CmdTask(name="build", cmd="make", retries=0)` binds as it reads,
and pyright completes every forwarded keyword and rejects a misspelled one —
so a keyword added to `BaseTask` reaches every subclass through one `TypedDict`.

A subclass that accepts **fewer** keywords than its parent forwards a narrower
`TypedDict` (`CheckTaskParams` for `HttpCheck`/`TcpCheck`) **and** calls a
`reject_*_params` guard, because a hand-written `zrb_init.py` is not
type-checked and `**kwargs` would otherwise pass an excluded keyword through
to the parent, where it is accepted and then ignored. State the exclusion in
the constructor docstring too; `test_a_forwarding_constructor_names_the_set_it_forwards`
requires a forwarding docstring to name the class its keywords come from,
since `help()` shows only `**kwargs`.

Shadowing a parent's default (`LLMChatTask` drops `retries` to 0) is
`kwargs.setdefault(...)` plus an entry in `test_constructor_surface.py`'s
`deliberate_shadowing` — pyright rejects a keyword parameter that also appears
in the unpacked `TypedDict`.

### Config Conventions

Boolean `CFG`/env knobs follow a naming rule (ADR-0026):

- **`<NAMESPACE>_ENABLED`** (state-last) when the toggle is the master switch of a namespace that has *other* settings, so it groups with its siblings — `WEB_AUTH_ENABLED` (alongside `WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES`), `LLM_SANDBOX_ENABLED`, `HOOKS_ENABLED`, `LLM_JOURNAL_ENABLED`.
- **Verb-first** (`ENABLE_`/`SHOW_`/`SEARCH_`/`INCLUDE_`/`ALLOW_`) for a standalone on/off behavior with no sub-config namespace — `LLM_ENABLE_BUILTIN_SKILLS`, `LLM_SEARCH_PROJECT`, `LLM_SHOW_TOOL_CALL_DETAIL`.

When **renaming** a released knob, preserve the old env key via `EnvField(aliases=[new, old], write_key=new)` (reads either, writes the new form). A clean break is only safe pre-release. When **removing** one (or dropping an alias), add it to `RETIRED_SETTINGS` in `config/retired.py` with what replaces it, so zrb names it at startup instead of silently ignoring it. A removed top-level `zrb` export goes in `_RETIRED_EXPORTS` in `zrb/__init__.py` the same way.

### Imports

Default to module-level imports. An in-function import must justify itself with a `# lazy: <reason>` comment matching one of:

1. **Heavy third-party deferral** — `pydantic_ai`, `prompt_toolkit`, `mcp`, `fastapi`, `boto3`, `anthropic`, `openai`, `chromadb`, `playwright`, and other extras-marked packages.
2. **Transitively heavy via internal** — an internal `zrb.*` module that eagerly imports a heavy package inherits the rule. Hoisting silently re-introduces the slow load.
3. **Circular import** — name the cycle: `# lazy: circular — tool → ui → llm_task → here`.
4. **Test patch seam** — tests patch at the source path and rely on the patch taking effect inside a consumer; hoisting binds the name at consumer-load time and bypasses the mock. Tag: `# lazy: tests patch <path>; hoisting bypasses the mock`.
5. **Platform-only module** — the module does not exist on every supported platform (`msvcrt`, `fcntl`, `termios`), or is reached on only one of them and costs real import time on the others. Tag: `# lazy: platform-only — <which platform, and what the others would pay>`. When the *whole* module needs the name, a module-level `try: import X / except ImportError: X = None` is the better shape (see `fcntl` in `llm/tool/journal_write.py`); the in-function form is for a single platform-guarded branch.

`# noqa: F401` belongs only on imports that exist as a test-patch attribute on the module itself — verify the patch targets working code; a patch against a name nothing reads should be deleted, not preserved.

`flake8 src/zrb --select=F` runs as part of `./zrb-test.sh` and fails on unused or duplicate imports.

### Test Guidelines

**Principles** (ADR-0034):

- **Coverage:** ≥ 95%
- **Public API only.** NEVER access or test private members (anything `_prefix`). If internal behavior is hard to test publicly, refactor the class to expose a public hook or property.
  - The usual seam for a private helper is **the public entry point plus the boundary the helper's effect crosses** — drive the public function, then assert on what reached the mocked dependency. `test/llm/tool/test_code_analyze.py` does this: `analyze_code` is the entry point, `run_agent` is the boundary, and patching `CFG` steers the thresholds, so the private helpers' behavior is verified without naming either.
  - Mocking a *public* dependency the module imported (`run_agent`, `llm_limiter`) is not a private-member access; mocking `_private_helper` is.
- Use `pytest` fixtures and mocks for external dependencies.
- Follow Arrange-Act-Assert (AAA).

**Test file conventions:**

- ❌ No suffixes like `_advanced.py`, `_coverage.py`, `_extra.py`, `_comprehensive.py`
- ✅ Single source of truth: update the main test file (`test_manager.py`), not a sibling
- ✅ Split files >500 lines by **feature group** (`test_manager_lifecycle.py`, `test_manager_search.py`), not by depth or coverage level
- ⚠️ Mirroring `src/` produces **duplicate basenames** (`test_registry.py` under `llm/agent/subagent/`, `llm/hook/`, `llm/prompt/`, `llm/skill/`, `llm/tool/`, …). pytest imports rootdir-relative, so two bare `test_registry.py` files collide at collection. Fix by adding an empty `__init__.py` to the test directory. Keep the mirrored filename; do not rename the test to dodge the clash.

**Type checking:** the tree runs at pyright `standard`, with a `strict` array in `pyrightconfig.json` naming the packages held to `strict` (`callback`, `dot_dict`, `group`, `input`, `session`, `session_state_logger`, `xcom`). `./zrb-test.sh` gates both through the one `pyright src/zrb` call. Add a package to that list once it is strict-clean; never remove one. Prefer fixing the *root* of an inference failure over annotating each site that inherits it — when `builtin/` was first checked, one unannotated parameter in `util/cli/style.py` accounted for 335 of its strict errors.

**Coverage exclusions** (`.coveragerc`) — do not test these directly:

- `any_*.py` — protocols / interfaces (no implementation)
- `__main__.py` — entry points (tested via integration)
- `__init__.py` — re-exports only
- `zrb_init.py` — user-defined initialization, not library code
