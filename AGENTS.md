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
- `src/zrb/config/` — `CFG` singleton, composed from mixins under `mixins/`. **`CFG.FOO` access stays flat** regardless of which mixin owns the attribute.
- `src/zrb/task/` — task engine: `BaseTask`, `Task`, `CmdTask`, `HttpCheck`, `TcpCheck`, `Scheduler` (extends `BaseTrigger`), `Scaffolder`, `RsyncTask`. Plus the `make_task` decorator.
- `src/zrb/llm/` — LLM integration. `task/llm_task.py` (`LLMTask`) and `task/chat/task.py` (`LLMChatTask`) are `BaseTask` subclasses that create pydantic-ai agents internally. `prompt/` composes the system prompt; `tool/` ships agent-callable tools; `agent/subagent/` handles delegation; `common_tools.py` registers the shared baseline used by `LLMChatTask`, `LLMTask`, and `SubAgentManager`.
- `src/zrb/llm_plugin/` — built-in LLM plugin: `core_skills/` (always-on methodology baseline), `skills/` (utility skills, gated by `CFG.LLM_ENABLE_BUILTIN_SKILLS`), `agents/` (sub-agents, gated by `CFG.LLM_ENABLE_BUILTIN_AGENTS`). Each skill is `SKILL.md` or `SKILL.py`; each agent is `*.agent.md`. The toggles suppress only built-in content — user/project/plugin skills and agents always load. See ADR-0052.
- `test/` — mirrors the `src/` hierarchy. The mirror is a *naming* rule, not a completeness claim: where a test exists it sits at the mirrored path, but plenty of modules have no test file of their own and are covered through a caller instead.

> For a top-down tour of `zrb llm chat "..."` (CLI → task → agent run → UI → history), see `docs/advanced-topics/llm-chat-lifecycle.md`.

## LLM Prompt System

`PromptManager` (`src/zrb/llm/prompt/manager.py`) assembles the system prompt from ordered sections. Default order in `config/mixins/llm_prompt.py::DEFAULT_LLM_INCLUDE_SECTIONS`:

`persona → workflow → examples → system_context → project_context`

- `persona` — identity and response style.
- `workflow` — the whole rulebook. Opens with the **Priority Order** (one ladder, precedence not sequence — first, because primacy bias means later rules get dropped first), then how a turn runs: Turn Sequence, project-doc reading, skill activation, the Working Loop, the Verify Before Done gate, Recovery, Stop, and a closing **Final Reminders** recap. Owns the `When you don't know` ladder, the `Where the deliverable goes` rule, the `Tool usage` cross-tool policy, the `Delegating to sub-agents` triggers, and the one git rule a policy cannot produce (show `git status` + `git diff HEAD` before asking approval). Carries the skill catalogue via `{CORE_SKILLS}` / `{AVAILABLE_SKILLS}` / `{PREACTIVATED_SKILLS}` (`build_skill_replacements` in `prompt/claude.py`).

  The Working Loop is **Understand → Diagnose → Plan → Execute → Verify → Reply**. `Diagnose` is a named step, not a hint inside `Understand`: name the cause and the observation supporting it before choosing a fix. It was absent for eleven releases and survived only as two scattered fragments — "reproduce a bug before changing code" in `Understand` and "a symptom fixed with the root cause alive" in the Verify checklist — so the loop went gather → act with no gate between them, which is the shape symptom-patching takes. `Understand` also states the search discipline the loop assumed: state the hypothesis and what would rule it out, then search for *that*. Grepping with no hypothesis returns hits instead of answers.

  `When you don't know` covers the "I lack information" cases; its third rung covers the other kind. Two defensible options is neither a tool call nor a coin flip: name the two or three criteria that decide it, score both, recommend one. Asking without the criteria spends a round-trip the criteria would have closed.

  **`Final Reminders` exploits recency the way `Priority Order` exploits primacy.** Both ends of the prompt are privileged positions and only one was used; the recap is ~70 tokens restating the six rules that go wrong most often, and it is the pattern kimi's "Ultimate Reminders" and gemini's "Final Reminder" occupy in opencode. It is duplication *by design*, which the MECE rule permits inside one section and only inside one section. What it may never do is introduce a rule of its own — that splits the rulebook and the half nobody edits is the half the model reads last. `test_section_composition.py::test_the_closing_recap_restates_only_what_the_body_states` asserts every recapped rule is still stated in the body above it, per preset.
- `examples` — demonstrations only, no rules of their own; profile-gated.
- `system_context` — *stable* runtime facts only (OS, CWD, model, detected tools/markers) plus the `<live-context>` anchor, so the cached prefix stays byte-identical across turns. It announces only the one model-adaptive exception — a model the capability registry deny-lists for parallel tool calls (ADR-0038) — never an affirmative batching line.
- `project_context` — project docs found (mandatory read) and, listed separately, home-level docs (`~`, `~/.claude`) which are *not* project overrides.

Volatile per-turn state (time, git, todos, worktree, mode, interactivity) lives in `live_context`, not `system_context` — it is injected into the latest user turn. `render_live_context` also performs the per-turn ambient wiring: session binding for the todo tools, interactive-mode binding for `ask_user_question`, stale-worktree cleanup.

Override the section list with the `include_sections` constructor parameter or `ZRB_LLM_INCLUDE_SECTIONS` (comma-separated, order-sensitive). A name that is **not** a built-in resolves as a custom, config-positioned section (precedence: built-in > registered provider > markdown file):

- **Registered provider** — `prompt_manager.register_section("company_context", lambda ctx: ...)` composes by calling the provider with the active context. Use for always-on content reflecting runtime state. Return `""` to emit nothing. This is also the migration path for code that used to register tool guidance.
- **Markdown file** — otherwise the name resolves via `get_prompt(name)` (project override → env → base prompt dir → package), so `company_context` loads `company_context.md` with `{PLACEHOLDER}` substitution. A missing file resolves to `""` and logs a warning at compose time.

See ADR-0044.

### Where a rule goes

**Rules live where they are enforced (ADR-0045).** Sort every rule by what can make it true: **the runtime** (a hook, a tool policy, a tool implementation), then **the tool's own docstring** (per-tool mechanics, next to the schema), then **the prompt** (only judgment no tool can make), then **a skill** (domain methodology, on demand). It is why the prompt holds three rule sections and no tool catalogue: a per-tool rule belongs in the docstring, and a rule a policy already enforces belongs nowhere in the prompt at all.

**Each section is MECE — a single behavior lives in exactly one section.** Adding a rule: first check whether it belongs in the prompt at all, per the ladder above; then pick the smallest-scope section that owns the concept.

**Moving prose into a docstring does not save tokens.** A *registered* (non-deferred) tool's docstring *and* parameter schema ship into every request. The only lever on tool-definition weight is the **number** of tools visible per request — hence the conditional registration of LSP, worktree, plan-mode and journal tools, and `defer_loading=True` on rarely-used ones (a deferred tool's name stays discoverable through native tool search; its schema materializes only when the model searches for it). Relocating into a docstring buys locality and adherence, not size. See ADR-0056.

> **Invariant: every section reads whole on its own.** Sections toggle independently, so a section that cites a sibling reads fine by default and dangles the moment someone trims the list. The fix is always to **restate the rule compactly in place**, never to add the pointer back. Where a reference is genuinely worth keeping, wrap it in `<!--requires:other_section-->`. There are two such guards, both in `workflow`: its pointer at `project_context`, and the clause withdrawing the batch-by-default rule for a model `system_context` reports as unable to batch. `test_section_composition.py` brute-forces all 7 subsets against an `OWNED_VOCABULARY` map. **Adding a section-defining term means adding it to `OWNED_VOCABULARY`; renaming one means renaming it there too** — the subset walk asserts a negative, so a term the prompt no longer contains keeps passing while guarding nothing. `test_every_owned_term_still_exists_in_its_owner` catches that, and the test only knows the vocabulary it is told about. See ADR-0046.

**A docstring may never point at a prompt section.** The requires-guard only strips prompt→prompt references; a docstring→section pointer dangles with nothing to catch it, since a tool ships with its schema regardless of `LLM_INCLUDE_SECTIONS`. `ActivateSkill` used to say "as listed under Core Skills / Available Skills"; it now describes the argument and lets an unknown value come back with the valid ones listed — the runtime resolving what a pointer used to defer. `test_skill.py::test_description_does_not_point_at_a_prompt_section` pins it.

Consistent duplication is the cost of independent toggling; **divergent** duplication is the bug. The current split follows the ladder: *when* to delegate is judgment, so `workflow` owns the triggers; *how* (agent roster, envelope mechanics) stays in `DelegateToAgent`'s docstring as the single source.

### Profile (a preset over three axes)

`ZRB_LLM_PROFILE` (`CFG.LLM_PROFILE`, default `auto`) selects a **preset**: a named binding of *which* sections compose, *how* they are phrased, and *which* tools register (ADR-0075). The table lives in `prompt/profile.py::PRESETS`.

| Preset | sections | phrasing variant | tool surface | composed prompt |
|---|---|---|---|---|
| `full` | default | — | all 20 eager tools (3,840 tok) | 4,583 tok |
| `lean` | default | `.lean` | all but `LEAN_DROPS` (17 eager, 3,146 tok) | 4,038 tok |
| `minimal` | `persona, workflow, system_context` | `.minimal` | `MINIMAL_TOOLS` (10, 2,339 tok) | 1,242 tok |

The names order themselves by how much the model is asked to hold at once. That is the point of them: the previous set (`terse`/`mini`/`micro`) mixed a prose register with two size words, named the *largest* preset "terse", and put `micro` in collision with the vendor tier labels the selector matches on — a model labelled `-micro` matched nothing and fell through to the heaviest preset.

- `auto` resolves from the model id: a declared parameter count ≤4B → `minimal`, 5–14B or a vendor small-tier label → `lean`, otherwise `full`. zrb makes **no guess from a family name** — `deepseek`/`qwen`/`llama` span tiny→frontier — but a stated parameter count is the vendor declaring the size. Declare your own with `register_model_profile("my-7b", "lean")`; user declarations beat the built-ins.
- **A stated count is parsed as a number** (`builtin_profile` → `SIZE_BANDS`), never matched per band by a digit pattern. A digit class cannot see a decimal point: `deepseek-r1:1.5b` matched `5b` and took `lean`, so the two most-run local models on the planet got the preset for models ten times their size. Parsing also fixes the two ambiguous ids by rule — the *first* count wins (`qwen3-30b-a3b` reads as 30B, its total, not its active parameters) and a count outranks a label (`some-mini-32b` stays `full`).
- The bands are asymmetric on purpose: `lean` keeps every section and nearly every tool, so a false positive is cheap; `minimal` *removes* both, so a stated ≤4B count selects it outright. A vendor label alone still does not — `nano`/`micro` sit on models far stronger than a 3B local one (`gpt-5-nano`) and stay on `lean`.
- **A small-tier label plus a local provider prefix does reach `minimal`** (`LOCAL_PROVIDERS`). The label is a claim about a lineup; the prefix says who is serving it. `openai:gpt-5-nano` is the entry tier of a hosted family, `ollama:phi4-mini` is 3.8B of weights on a laptop, and both state no count — so both used to take `lean`, handing the 3.8B model the heaviest composition in the system. `ollama:`'s hosted tier is excluded by its `:cloud` suffix, which is what keeps `ollama:kimi-k2.6:cloud` on `full`.
- An explicitly-set `ZRB_LLM_INCLUDE_SECTIONS` overrides a preset's section list; changing `CFG.DEFAULT_LLM_INCLUDE_SECTIONS` does not (a preset outranking a *default* is the intended precedence).
- Registering a fourth preset is `register_preset("nano", Preset(...))`. `valid_profiles()` derives from `PRESETS`, so the new name is immediately accepted by `ZRB_LLM_PROFILE` and `register_model_profile`. A bare `PRESETS[name] = ...` still works and skips the checks — which is why `Preset.__post_init__`, not `register_preset`, is what rejects setting `tools` and `drops` together.

  **The three built-ins get invariants a custom preset does not.** `PRESET_VARIANTS` in `test_section_composition.py` is a hardcoded list of three, so the rank-1 safety floor, the burden ladder and the tool-closure checks all stop at `minimal`. `register_preset` re-checks the part that is checkable at runtime and warns: a `variant` with no `{section}.{variant}.md` on the lookup path (which silently ships the *frontier* prose to a preset written for a 1B model), a composed rulebook missing one of the rank-1 concepts, and a section list carrying no rulebook at all. Warnings, not errors — a custom rulebook may phrase a rule in words `_RANK_ONE_PATTERNS` does not match, and a preset that varies only some sections is legitimate. That table is deliberately a second copy of the test's: a shared one would let a single wrong regex excuse both.

**One naming convention, no exceptions.** A section named `foo` resolves `foo.{profile}.md` and falls back to `foo.md`. That is how *every* preset varies text — `workflow.lean.md`, `workflow.minimal.md`, `examples.lean.md`. There is no such thing as a `workflow_lean` *section*: the section list only ever says which topics appear, never which wording. A preset ships files only for the sections whose text actually changes.

**Burden falls monotonically with target capability.** That is what the preset ladder is *for*, and it is asserted, not assumed:

> Each rule-carrying section (`persona`, `workflow`) must be strictly smaller in mass and rule count than the same section one preset up, **measured per section**. Clause nesting must not rise. `test_section_composition.py::test_rule_burden_falls_as_the_target_model_gets_weaker`.

**Per section, not summed.** A summed measure reports the total and hides its terms. `persona` had no variant at any preset, so all three shipped the same 486 tokens of frontier-register prose — 35% of `minimal`'s whole rule payload, telling a ~3B model to distinguish `file:line` from `file:symbol` and contradicting its own rulebook on reply length — and the sum still fell, because `workflow.minimal.md` shrank enough to cover for it. **A section that never varies is a section whose variant nobody wrote**, and the silent `foo.{profile}.md` → `foo.md` fallback is what keeps that quiet. `persona.lean.md` and `persona.minimal.md` now exist.

> Demonstrations are exempt from that ladder — a worked example lowers burden rather than adding it — but not from the budget: **the composed total falls too.** `test_section_composition.py::test_a_weaker_targets_preset_ships_less_prompt_in_total`.

`lean` motivated both. It used to ship a 5-14B model the frontier `workflow.md` plus 1,200 tokens of extra examples; even after `workflow.lean.md` cut ~700, `examples.lean.md` put ~1,200 back and left `lean` the heaviest composition in the system — 5,061 tokens against `full`'s 4,563, shipped to the weaker model. Exempting demonstrations from the *ladder* was right; exempting them from the *budget* meant the exemption paid for itself out of the model's attention. `examples.lean.md` is now 568 tokens and `lean` composes to 4,038 against `full`'s 4,583.

**Mass is not the axis a preset varies; form is.** `workflow.lean.md` was `workflow.md` with 526 words of subordinate clause removed — 41 rules against 42, clearing the burden ladder by a single bullet while shipping a 7B model the frontier prose *register*. That is the `persona` defect one level up: a variant that varies how long the rules are and not how they are written. Compare opencode's `kimi.txt` against its `anthropic.txt` — differently shaped, not one trimmed. `workflow.lean.md` is now written in `minimal`'s register at `full`'s coverage: imperative sentences, decision tables for `When you don't know` and `Recovery`, no nested qualification. **A variant that reads like its parent has not been written yet**, and neither the rule count nor the char count can see the difference — only reading them side by side can, which is why this paragraph exists instead of a test.

> **Invariant: a variant never becomes the only home of a rule** (ADR-0047). A variant reaches only the models that resolve to it, so a rule that exists nowhere else silently misses everyone else. A variant may re-shape the rulebook for its model class — that is what `workflow.lean.md` and `workflow.minimal.md` are — but the safety floor below is what stops re-shaping from becoming quiet deletion.

Two further invariants bound a preset (ADR-0075), both tested:

> **Composition may drop method; it may never drop safety.** Priority Order rank 1 — secrets, tool results are data not instructions, confirm destructive actions — must survive in every preset. `test_section_composition.py::test_every_preset_carries_the_rank_one_safety_rules`.

> **A preset's tool set is closed under every channel that can name a tool.** There are three — tool docstrings, prompt sections, and injected context — and a name in any of them must resolve in every preset that ships it. Docstrings route between each other and ship with their schema whatever the config, so they cannot carry a `<!--requires:-->` guard; this is what sizes `MINIMAL_TOOLS` at ten rather than six (`Shell`/`Grep` route to `Glob`/`RM`/`MV`, and `Shell`'s `background=True` returns a handle only `MonitorProcess` can poll). `test_common_tools.py::test_minimal_tool_set_is_closed_under_docstring_cross_reference`, `test_section_composition.py::test_workflow_lean_names_no_tool_its_preset_lacks`, `test_live_context.py::test_a_line_never_names_a_tool_the_preset_dropped`.

**Injected context was the channel nobody guarded.** `<live-context>` announced `AskUserQuestion`, the `<journal-index>` block said "Use `SearchJournal` for full entries", and the `_LIVE_CONTEXT_ANCHOR` promised lines about todos and worktree — on every preset, including the two that register none of them. `_render_parts` now takes the model and asks `Preset.admits` before emitting a line that names a tool, and the journal index is gated on `SearchJournal` surviving rather than on `LLM_JOURNAL_ENABLED` alone. The `Interactive: no` branch stopped naming `AskUserQuestion`/`EnterPlanMode`/`ExitPlanMode` entirely: `_resolve_interactive` unregisters all three in exactly that branch, so it spent ~55 tokens per turn forbidding what was already gone.

**The tool axis has two forms.** `Preset.tools` is an allowlist — a closed, fixed surface, which is what makes `minimal`'s closure checkable. `Preset.drops` is a denylist, which is what `lean` needs: it keeps the full surface and subtracts `LEAN_DROPS`, so an allowlist would have to re-list every tool and would silently drop each new one from `lean` until someone remembered it. `LEAN_DROPS` is the journal trio (cross-session memory is the wrong thing to spend a constrained model's tool budget on). `Shell` is the only shell tool (ADR-0064), so there is no second shell tool to drop — a Claude-authored sub-agent that lists `Bash` maps onto `Shell` when it loads.

**A preset with a *closed* surface registers its tools eagerly.** `defer_loading` trades a tool's schema for a `search_tools` entry the model must call before it can reach the tool. That pays when it hides a dozen tools; it inverts at ten — `minimal` would spend ~146 tokens of `search_tools` to hide `MonitorProcess`'s ~127, and charge a ~3B model a discovery turn to poll a background process. `lean` keeps 17 eager tools and 13 deferred, where the indirection is the whole saving, so its deferred tools stay deferred: `_Surface.undefer` is keyed on `Preset.tools is not None`, not on "is the axis constrained at all" — the same question only while `minimal` was the only preset that constrained it. `_selected` un-defers what a closed preset keeps; `test_common_tools.py::test_minimal_registers_no_deferred_tools` covers the factory path too, since `MonitorProcess` is factory-built and is the only deferred tool the preset keeps.

`examples` is deliberately thin in the base: it keeps only the examples that fix a zrb-specific stance a capable model would not otherwise adopt, and the rest live in `examples.lean.md`. Add a demonstration to the variant unless it teaches a stance a frontier model gets wrong.

`examples.lean.md` is thin now too, and for a different reason: half of it had become a second rulebook. Six of its fourteen demonstrations restated a rule `workflow.lean.md` already states crisply — "Do it, don't announce it" against the Execute bullet, "Finish the change" against rank 4, "Deliver every part of a numbered ask" against Completeness. A demonstration earns its place by teaching what prose cannot: **scale** (`2 + 2` → `4`), **stance** (a proposal investigates then waits), or a *form* a rule can only describe (a 44-site migration as N `Edit` calls rather than one payload). Before adding one, check whether the rule above it already says the same thing in fewer tokens.

> **Invariant: `examples` demonstrates, it never legislates.** No `Wrong:` verdict, and no variant that embeds the base verbatim. Both were true by convention and false in fact: `examples.lean.md` carried three `Wrong:` clauses and opened with `examples.md` byte-for-byte. A `Wrong:` clause is a rule wearing a demonstration's clothes, and it lands in the one section `minimal` drops and the burden ladder excludes — two ways for a rule to go missing quietly. A variant must cover what the base teaches (`BASE_EXAMPLE_CONCEPTS`, matched on stance so the wording may differ) without copying how it says it. `test_section_composition.py::test_examples_carry_no_rule_of_their_own`, `::test_a_variant_of_examples_is_not_a_superset_of_the_base`, `::test_a_variant_of_examples_still_teaches_what_the_base_teaches`.

One call resolves the knob and the model together — `profile.active_preset(model)` — and each consumer takes the axis it owns: `PromptManager.active_sections` the section list, `_get_composed_middlewares` the phrasing variant, `apply_common_tools` the tool surface. The tool axis is a predicate (`_preset_tool_filter`) applied to both the static list and every tool factory, because a factory resolves per run; a constrained preset also drops MCP toolsets, whose tool lists are unknown at registration and so cannot be part of a closed surface.

### Journal

The cross-session journal is **three tools and no prose** (ADR-0053). `SearchJournal` reads; `LogActivity` appends one line to `activity-log/YYYY/YYYY-MM/YYYY-MM-DD.md`; `WriteJournalNote` writes a topic note under `user/`, `preferences/`, `projects/`, or `technical/`. The writers (`llm/tool/journal_write.py`) derive every path and timestamp themselves and maintain the index and backlink graph, which is why the four invariants the old linter checked — no broken links, no missing backlinks, no orphans, no missing indexes — are unviolatable rather than checkable. What earns an entry lives in the tool docstrings.

`LLM_JOURNAL_ENABLED=false` unregisters all three tools in `apply_common_tools`; `render_journal_index` checks the same flag for the `<journal-index>` injection. There is no prompt section to suppress.

### Ambient State (`ContextVar`s)

Canonical index in `src/zrb/contextvars.py` — every var, its owning module, and its typed wrapper.

- **Reading:** prefer the wrapper.
- **Scoped writes:** use the underlying `ContextVar` (`token = var.set(...)` then `var.reset(token)`). Canonical pattern in `agent/run/runner.py`.

### Worktree Storage

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
- **`Mixin` means reusable** (ADR-0035). Suffix a class `Mixin` only when it reads no state it does not itself set, so any class can mix it in (`BufferedOutputMixin`; the `CFG` mixins under `config/mixins/`). A class that reads attributes only one host provides is a *part* of that host: name it `<Owner><Aspect>` in a file named for the aspect — `ChatExecution` in `task/chat/execution.py`, `BaseUICommands` in `ui/base/commands.py`. No `_mixin` suffix, no leading underscore (these are imported across modules, so "module-private" would be a false claim). Parts keep a `TYPE_CHECKING` host-contract block declaring what the host must provide. **A method the host calls by name, a sibling part declares, or a subclass overrides is public too** — `LLMTaskHistory.get_conversation_name`, `LLMTaskBuilding.get_model`. Only helpers called from inside their own part keep the underscore.
- **No path stutter.** `X/manager/manager.py` is `X/manager.py`; siblings become `X/manager_<aspect>.py`.
- **Error handling:** an LLM tool error the *model* has to recover from carries a `[SYSTEM SUGGESTION]` prefix with actionable guidance. Ordinary programmer errors (bad argument, broken invariant) stay plain `ValueError`/`RuntimeError` — the prefix is for text the model reads, not for every raise.

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

`# noqa: F401` belongs only on imports that exist as a test-patch attribute on the module itself — verify the patch targets working code; cargo-cult patches against names nothing reads should be deleted, not preserved.

`flake8 src/zrb --select=F` runs as part of `./zrb-test.sh` and fails on unused or duplicate imports.

### Test Guidelines

Run: `source .venv/bin/activate && ./zrb-test.sh [path]` — pass nothing for all, or a file / directory / `file::test_function` path to scope.

**Principles:**
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
