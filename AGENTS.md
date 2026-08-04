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
- `src/zrb/llm_plugin/` — built-in LLM plugin, split into three categories: `core_skills/` (always-on methodology baseline the utility skills delegate into), `skills/` (utility skills, gated by `CFG.LLM_ENABLE_BUILTIN_SKILLS`), and `agents/` (sub-agents, gated by `CFG.LLM_ENABLE_BUILTIN_AGENTS`). Each skill is `SKILL.md` or `SKILL.py`; each agent is `*.agent.md`. The toggles suppress only built-in content — user/project/plugin skills and agents always load. See ADR-0069.
- `test/` — mirrors the `src/` hierarchy. The mirror is a *naming* rule, not a
  completeness claim: where a test exists it sits at the mirrored path, but
  plenty of modules have no test file of their own and are covered through a
  caller instead.

> For a top-down tour of `zrb llm chat "..."` (CLI → task → agent run → UI → history), see `docs/advanced-topics/llm-chat-lifecycle.md`.

## LLM Prompt System

`PromptManager` (`src/zrb/llm/prompt/manager.py`) assembles the system prompt from ordered sections. Default order in `config/mixins/llm_prompt.py::DEFAULT_LLM_INCLUDE_SECTIONS`:

`persona → workflow → examples → system_context → project_context`

Three carry rules, two carry runtime facts. User-added prompts follow. Override via the `include_sections` constructor parameter or the `ZRB_LLM_INCLUDE_SECTIONS` env var (comma-separated, order-sensitive).

> **Rules live where they are enforced (ADR-0098).** Sort every rule by what can make it true: **the runtime** first (a hook, a tool policy, a tool implementation), then **the tool's own docstring** (per-tool mechanics, next to the schema), then **the prompt** (only judgment no tool can make for the model), then **a skill** (domain methodology, on demand). This is what collapsed six rule sections into three. It also means *there is no prompt-side tool catalogue*: `tool_guidance` and its `add_tool_guidance` registry are gone (ADR-0100), and `mandate` / `git_mandate` / `journal_mandate` are gone with it (ADR-0098, ADR-0099). Those names in a pinned config now resolve to an empty custom section and log a warning.

> **Moving prose into a docstring does not save tokens.** pydantic-ai serializes every registered tool's docstring *and* parameter schema into every request, so a docstring is not deferred context. Relocation buys locality and adherence. The only lever on tool-definition weight is the **number** of registered tools — hence the conditional registration of LSP, worktree, plan-mode, and journal tools, and `defer_loading=True` on the rarely-used ones.

A section name that is **not** a built-in resolves as a custom, config-positioned section (precedence: built-in > registered provider > markdown file):
- **Registered provider** — `prompt_manager.register_section("company_context", lambda ctx: ...)` registers a dynamic provider, composed by calling it with the active context at compose time. Use for always-on content that reflects runtime state (current sprint, deploy target, live schema). Return `""` to emit nothing. **This is also the migration path for code that used to call `add_tool_guidance`.**
- **Markdown file** — otherwise the name resolves via `get_prompt(name)` (project-override → env → base-prompt-dir → package), so `company_context` loads `company_context.md` with the usual `{PLACEHOLDER}` substitution. Missing files resolve to `""` (harmless no-op; a warning is logged at compose time so an unknown/misspelled name is diagnosable).

Either way, downstreams add ordered sections without editing `PromptManager`. See ADR-0061.

### Profile (model-adaptive phrasing)

A second axis controls *how* each section is phrased, independent of *which* sections appear (ADR-0083). The `ZRB_LLM_PROFILE` knob (`CFG.LLM_PROFILE`, default `auto`) selects a **profile**:

- `terse` / `mini` — force that profile. `terse` is the concise, principle-led base; `mini` is the same rules plus worked demonstrations, for small models.
- `auto` (default) — resolves to `mini` when the model id declares a small size (a parameter count ≤14B, or a vendor small-tier label), `terse` otherwise; a user mapping overrides either (ADR-0093). zrb still makes **no guess from a family name** — `deepseek`/`qwen`/`llama` span tiny→frontier — but a stated parameter count is the vendor declaring the size, not an inference. Declare your own with `register_model_profile("my-7b", "mini")` (`prompt/profile.py`); user declarations beat the built-ins. See `resolve_profile` and `DEFAULT_MODEL_PROFILES`.

The base `*.md` files **are** the `terse` profile. Other profiles are **variant overlays**: `get_prompt(name, profile="mini")` resolves `{name}.mini.md` through the full override chain, falling back to the base `{name}.md` when no variant exists — so a profile only needs variant files for the sections that actually change (currently `examples.mini.md`, the only variant). **A variant may add demonstrations; it may not add or re-phrase rules** (ADR-0091): `mini` is `terse` plus worked examples, never more rule text. A variant *replaces* its base file, so `examples.mini.md` must stay a strict superset of `examples.md` — a test pins that.

> **`examples` is deliberately thin in the base.** Its own first line says it carries illustrations and *"no rules of their own"*, which makes it the one section where the profile axis can do real work: the base keeps only the four examples that fix a zrb-specific stance (no forced codebase tie-in, directive→disk with call sites, measure before you call something large, tool result carrying an imperative), and the rest live in `examples.mini.md`. Adding a demonstration? It goes in the variant unless it teaches a stance a frontier model gets wrong — and if it teaches a *rule*, it does not belong in either file. `examples` survived the collapse to three sections precisely because demonstrations are the highest-value content per token for the small models the profile axis serves.

> The profile was previously called `explicit`; it is `mini` now (ADR-0095), naming the model class it targets rather than a register it no longer uses. This is a clean break — `ZRB_LLM_PROFILE=explicit` is not recognized and falls through to `auto`.

`PromptManager._get_composed_middlewares` resolves the profile once (from `CFG.LLM_PROFILE` + `self._model`) and threads it to file-backed sections. Cross-cutting voice that does not decompose into a variant stays a whole alternate section/preset (the selection escape hatch).

> **Invariant: a behavioral rule never lives only in a profile variant.** A variant reaches only the models that resolve to it, so a rule placed there silently misses everyone else. Variants may re-phrase, repeat, or exemplify a rule; the rule itself belongs in the base file. (This was a real bug twice over: "when you say you will run a tool, actually run it" lived only in the variant and never shipped — it is now in `workflow.md` → Execute — and before ADR-0093 the registry shipped empty, so `auto` resolved to `terse` for *every* model and the variant reached nobody at all.)

> **Invariant: every section reads whole on its own.** Sections toggle
> independently via `LLM_INCLUDE_SECTIONS`, so a section that cites a sibling
> ("see the Priority Order", "per the Working Loop's triggers") reads fine in
> the default composition and dangles the moment someone trims the list. The
> fix is always to **restate the rule compactly in place**, never to add the
> pointer back. Where a reference is genuinely worth keeping, wrap it in
> `<!--requires:other_section-->` so it disappears with its target — with three
> sections there is exactly one such guard left, `workflow`'s pointer at
> `project_context`. `test_section_composition.py` enforces this by
> brute-forcing all 7 subsets against an `OWNED_VOCABULARY` map. **Adding a
> section-defining term means adding it to `OWNED_VOCABULARY`; renaming one
> means renaming it there too** — the subset walk asserts a negative, so a term
> the prompt no longer contains keeps passing while guarding nothing (`Cost of
> guessing wrong` and `ActivateSkill` both sat in the map for a release after
> the text dropped them). `test_every_owned_term_still_exists_in_its_owner`
> fails on that, and the test only catches vocabulary it knows about either way.

**Each section is MECE — a single behavior lives in exactly one section.** Adding a rule: pick the smallest-scope section that owns the concept — and first check whether it belongs in the prompt at all, per the enforcement ladder above.

The old tension between MECE and self-containment has largely dissolved: three sections means far fewer cross-references to keep in sync, and the case that used to force duplication (delegation triggers, needed by both `workflow` and `tool_guidance`) is gone with `tool_guidance` — `DelegateToAgent`'s docstring is now the single source, and `workflow` points at it rather than restating it. Where duplication is still unavoidable, consistent duplication is the cost of independent toggling; **divergent** duplication is the bug.

- `persona` — identity + response style
- `workflow` — the whole rulebook. Opens with the **Priority Order** (one six-rank ladder, precedence not sequence — first, because primacy bias means later rules get dropped first), then how a turn runs: the Turn Sequence (premise → first look → frame → skills → project docs), project-doc reading, skill activation, the Working Loop, the Verify Before Done gate, Recovery, Stop. Owns the `When you don't know` ladder, the `Where the deliverable goes` destination rule, the `Tool usage` cross-tool policy, and the one git rule a policy cannot produce (show `git status` + `git diff HEAD` before asking approval). Carries the skill catalogue via `{CORE_SKILLS}`/`{AVAILABLE_SKILLS}`/`{PREACTIVATED_SKILLS}` placeholders (`build_skill_replacements` in `prompt/claude.py`)
- `examples` — demonstrations only, no rules of their own; profile-gated
- `system_context` — *stable* runtime facts only (OS, CWD, model, whether the model supports parallel tool calls, detected tools/markers) plus the `<live-context>` anchor, so the cached prefix stays byte-identical across turns
- `project_context` — project docs found (mandatory read) and, listed separately, home-level docs found (`~`, `~/.claude`) which are *not* project overrides

Volatile per-turn state (time, git, todos, worktree, mode, interactivity) lives in `live_context`, not `system_context` — it is injected into the latest user turn. `render_live_context` also performs the per-turn ambient wiring (session binding for the todo tools, interactive-mode binding for `ask_user_question`, stale-worktree cleanup).

### Journal

The cross-session journal is **three tools and no prose** (ADR-0099). `SearchJournal` reads; `LogActivity` appends one line to `activity-log/YYYY/YYYY-MM/YYYY-MM-DD.md`; `WriteJournalNote` writes a topic note under `user/`, `preferences/`, `projects/`, or `technical/`. The writers (`llm/tool/journal_write.py`) derive every path and timestamp themselves and maintain the index and backlink graph, which is why the four invariants the old `journal-lint.py` checked — no broken links, no missing backlinks, no orphans, no missing indexes — are now unviolatable rather than checkable. What earns an entry lives in the tool docstrings.

`LLM_JOURNAL_ENABLED=false` unregisters all three tools in `apply_common_tools`; `render_journal_index` checks the same flag for the `<journal-index>` injection (ADR-0082). There is no prompt section to suppress.

### Ambient State (`ContextVar`s)

Canonical index in `src/zrb/contextvars.py` — every var, its owning module, and its typed wrapper.

- **Reading:** prefer the wrapper.
- **Scoped writes:** use the underlying `ContextVar` (`token = var.set(...)` then `var.reset(token)`). Canonical pattern in `agent/run/runner.py`.

### Worktree Storage

Git worktrees live at `{git_root}/.zrb/worktree/{branch_name}` (gitignored).


## Architecture Decision Records (ADRs)

Record a decision as an ADR in `docs/adr/` when it is **non-trivial** (a
reasonable developer could pick a different path), **consequential** (affects
other parts of the system or how users interact with it), and **persistent**
(meant to last, not a quick hack). One decision per record; mark a reversed
decision `Superseded by ADR-NNNN` rather than deleting it.

Mechanics — numbering, file layout, and the
Status/Context/Decision/Consequences/Alternatives/Evidence shape — live in
[`docs/adr/README.md`](docs/adr/README.md).

## Changelog

Lives under `docs/`: `changelog.md` (index), `changelog-v2/` (per-minor files,
e.g. `2.38.0.md`, `2.35.0-2.35.3.md`), `changelog-v1.md` (1.x archive). Entry
format and the compaction/collapsing procedure — with a worked example — are in
[Maintainer Guide → Changelog](docs/advanced-topics/maintainer-guide.md#changelog).

## Development Conventions

### Code Style
- Follow existing project conventions (formatting, naming, typing)
- **Modularity:** prefer functions under ~30 lines; helpers placed below their
  callers. This is a target for *new* code, not a repo-wide invariant — a few
  hundred existing functions exceed it (keybinding tables, hook creators,
  constructors). Going long is allowed when splitting would only scatter a
  single linear procedure; don't split just to hit the number, and don't cite
  the number as if it were enforced.
- **`Mixin` means reusable** (ADR-0085). Suffix a class `Mixin` only when it
  reads no state it does not itself set, so any class can mix it in
  (`BufferedOutputMixin`; the `CFG` mixins under `config/mixins/`). A class that
  reads attributes only one host provides is a *part* of that host, not a mixin:
  name it `<Owner><Aspect>` in a file named for the aspect — `ChatExecution` in
  `task/chat/execution.py`, `BaseUICommands` in `ui/base/commands.py`. No
  `_mixin` suffix, no leading underscore (these are imported across modules, so
  "module-private" would be a false claim). Parts keep a `TYPE_CHECKING`
  host-contract block declaring what the host must provide.
- **No path stutter.** `X/manager/manager.py` is `X/manager.py`; siblings become
  `X/manager_<aspect>.py`.
- **Error handling:** an LLM tool error the *model* has to recover from carries
  a `[SYSTEM SUGGESTION]` prefix with actionable guidance. Ordinary programmer
  errors (bad argument, broken invariant) stay plain `ValueError`/`RuntimeError`
  — the prefix is for text the model reads, not for every raise.

### Config Conventions

Boolean `CFG`/env knobs follow a naming rule (ADR-0073):

- **`<NAMESPACE>_ENABLED`** (state-last) when the toggle is the master switch of a namespace that has *other* settings, so it groups with its siblings — e.g. `WEB_AUTH_ENABLED` (alongside `WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES`), `LLM_SANDBOX_ENABLED`, `HOOKS_ENABLED`, `LLM_JOURNAL_ENABLED` (alongside `LLM_JOURNAL_DIR` / `_INDEX_FILE` / `_INDEX_MAX_CHARS`).
- **Verb-first** (`ENABLE_`/`SHOW_`/`SEARCH_`/`INCLUDE_`/`ALLOW_`) for a standalone on/off behavior with no sub-config namespace — e.g. `LLM_ENABLE_BUILTIN_SKILLS`, `LLM_SEARCH_PROJECT`, `LLM_SHOW_TOOL_CALL_DETAIL`.

When **renaming** a released knob, preserve the old env key via `EnvField(aliases=[new, old], write_key=new)` (reads either, writes the new form) so existing `ZRB_*` configs don't break. A clean break (drop the old key) is only safe pre-release.

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
  - The usual seam for a private helper is **the public entry point plus the boundary the helper's effect crosses** — drive the public function, then assert on what reached the mocked dependency. `test/llm/tool/test_code.py` does this: `analyze_code` is the entry point, `run_agent` is the boundary, and patching `CFG` steers the thresholds, so `_extract_info`/`_fit_file_payload` behavior is verified without naming either.
  - Mocking a *public* dependency the module imported (`run_agent`, `llm_limiter`) is not a private-member access; mocking `_private_helper` is.
- Use `pytest` fixtures and mocks for external dependencies
- Follow Arrange-Act-Assert (AAA)

**Test file conventions:**
- ❌ No suffixes like `_advanced.py`, `_coverage.py`, `_extra.py`, `_comprehensive.py`
- ✅ Single source of truth: update the main test file (`test_manager.py`), not a sibling
- ✅ Split files >500 lines by **feature group** (`test_manager_lifecycle.py`, `test_manager_search.py`), not by depth or coverage level
- ⚠️ Mirroring `src/` produces **duplicate basenames** (`test_manager.py` under
  `hook/`, `lsp/`, `snapshot/`, …). pytest imports rootdir-relative, so two
  bare `test_manager.py` files collide at collection. Fix by adding an empty
  `__init__.py` to the test directory — that qualifies the module name. Keep
  the mirrored filename; do not rename the test to dodge the clash.

**Coverage exclusions** (`.coveragerc`) — do not test these directly:
- `any_*.py` — protocols / interfaces (no implementation)
- `__main__.py` — entry points (tested via integration)
- `__init__.py` — re-exports only
- `zrb_init.py` — user-defined initialization, not library code
