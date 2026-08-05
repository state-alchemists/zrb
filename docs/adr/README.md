🔖 [Documentation Home](../README.md)

# Architecture Decision Records (ADR log)

This directory records **why** zrb is built the way it is — every significant
design decision, not just recent changes. Each record captures the context, the
decision, its consequences, the alternatives rejected, and **evidence** (where
the decision is visible in code or docs).

## How to read an entry

Every ADR uses the same shape:

- **Status** — Accepted / Superseded / Evolving.
- **Context** — the forces and problem that prompted the decision.
- **Decision** — what was chosen, concretely.
- **Consequences** — what this buys and what it costs.
- **Alternatives rejected** — and why.
- **Evidence** — file/doc pointers. Each rationale is tagged **[DOCUMENTED]**
  (stated in code/docs, usually quoted) or **[INFERRED]** (deduced from the
  code's structure; not written down anywhere). Inferred rationale is a
  best-effort reconstruction — correct it if you know the real story.

## How to add one

Create a new `docs/adr/adr-NNNN.md` file, take the next free `ADR-NNNN` number,
and add a row to the index below under the relevant theme section. One decision
per record. If a new decision reverses an old one, mark the old one
**Superseded by ADR-NNNN** rather than deleting it — the history is the point.

## Index

### Philosophy & architecture
- **ADR-0001** — Pure-Python task definitions, no YAML/DSL — [adr-0001.md](adr-0001.md)
- **ADR-0002** — Program against `Any*` interfaces, not concrete types — [adr-0002.md](adr-0002.md)
- **ADR-0003** — Async-first execution engine (`asyncio`) — [adr-0003.md](adr-0003.md)
- **ADR-0004** — Ambient state via `ContextVars`, not threaded arguments — [adr-0004.md](adr-0004.md)
- **ADR-0005** — Deferred f-string/Jinja rendering at execution time — [adr-0005.md](adr-0005.md)

### Task model
- **ADR-0006** — DAG dependencies via `>>` / `<<` operator overloading — [adr-0006.md](adr-0006.md)
- **ADR-0007** — Specialized task classes over one generic type — [adr-0007.md](adr-0007.md)
- **ADR-0008** — `@make_task` decorator alongside direct instantiation — [adr-0008.md](adr-0008.md)
- **ADR-0009** — Inputs and Envs as first-class objects — [adr-0009.md](adr-0009.md)
- **ADR-0010** — `zrb_init.py` hierarchical discovery + explicit registration — [adr-0010.md](adr-0010.md)
- **ADR-0011** — Retry, fallback, and successor as *tasks*, not exception handlers — [adr-0011.md](adr-0011.md)
- **ADR-0012** — Readiness checks as concurrent, task-based probes — [adr-0012.md](adr-0012.md)
- **ADR-0013** — `execute_condition` skips (not branches or exceptions) — [adr-0013.md](adr-0013.md)
- **ADR-0014** — Triggers and Scheduler as long-running daemon tasks — [adr-0014.md](adr-0014.md)
- **ADR-0015** — Explicit task lifecycle state machine — [adr-0015.md](adr-0015.md)
- **ADR-0016** — Capture declaration file/line for error attribution — [adr-0016.md](adr-0016.md)
- **ADR-0017** — Re-raise cancellation (`CancelledError`) after cleanup — [adr-0017.md](adr-0017.md)

### State & context
- **ADR-0018** — Three-tier context: SharedContext → Session → Context — [adr-0018.md](adr-0018.md)
- **ADR-0019** — XCom as per-task FIFO queues with callbacks — [adr-0019.md](adr-0019.md)
- **ADR-0020** — `DotDict` for attribute-style access to ctx data — [adr-0020.md](adr-0020.md)

### Configuration
- **ADR-0021** — `CFG` singleton composed from domain mixins, flat access — [adr-0021.md](adr-0021.md)
- **ADR-0022** — `EnvField` descriptor for env-backed config — [adr-0022.md](adr-0022.md)
- **ADR-0023** — Precedence: env var → default_factory → attribute default — [adr-0023.md](adr-0023.md)
- **ADR-0024** — Config reads `os.environ` only; `.env` is the task layer's job — [adr-0024.md](adr-0024.md)
- **ADR-0025** — `_ZRB_ENV_PREFIX` + `ROOT_GROUP_NAME` for white-labeling — [adr-0025.md](adr-0025.md)
- **ADR-0073** — Boolean config naming: verb-first for standalone toggles, `_ENABLED` for namespace switches — [adr-0073.md](adr-0073.md)
- **ADR-0084** — Named style themes: one `ZRB_THEME` preset supplies defaults for every style knob (LLM UI, markdown, CLI colors) via `EnvField(default_factory=...)`; individual `ZRB_*` env still overrides (relates to ADR-0021, ADR-0023, ADR-0083) — [adr-0084.md](adr-0084.md)

### Runners & packaging
- **ADR-0026** — One task definition, multiple runners (CLI + Web) — [adr-0026.md](adr-0026.md)
- **ADR-0027** — FastAPI + Uvicorn for the web runner — [adr-0027.md](adr-0027.md)
- **ADR-0028** — Nested CLI groups (`zrb <group> <task>`) — [adr-0028.md](adr-0028.md)
- **ADR-0029** — Battery-included builtin tasks, toggleable — [adr-0029.md](adr-0029.md)
- **ADR-0030** — Plugin/skill/agent discovery from directories — [adr-0030.md](adr-0030.md)
- **ADR-0031** — Scaffolder for template-based code generation — [adr-0031.md](adr-0031.md)
- **ADR-0032** — Poetry, single distribution, lazy heavy imports — [adr-0032.md](adr-0032.md)
- **ADR-0033** — Test discipline: ≥90%, public-API-only, F-only lint — [adr-0033.md](adr-0033.md)

### LLM core
- **ADR-0034** — pydantic-ai as the agent framework — [adr-0034.md](adr-0034.md)
- **ADR-0035** — MECE prompt sections via middleware composition — [adr-0035.md](adr-0035.md)
- **ADR-0036** — Self-managed history + two-tier summarization — [adr-0036.md](adr-0036.md)
- **ADR-0037** — Stream-error classification + cascading retry — [adr-0037.md](adr-0037.md)
- **ADR-0038** — Model capability registry + provider constraints — [adr-0038.md](adr-0038.md)
- **ADR-0039** — Markdown journal (dir + index) for long-term memory — [adr-0039.md](adr-0039.md)
- **ADR-0040** — Provider-agnostic, multi-vendor LLM support — [adr-0040.md](adr-0040.md)
- **ADR-0058** — History summarizer between deferred-tool iterations must not orphan tool-call metadata — [adr-0058.md](adr-0058.md)
- **ADR-0059** — Degenerate model output must not corrupt the conversation: scoped placeholder + empty-completion guard — [adr-0059.md](adr-0059.md)
- **ADR-0065** — Split volatile runtime state out of the system prompt into a per-turn `<live-context>` block to preserve prompt caching — [adr-0065.md](adr-0065.md)
- **ADR-0082** — Journal index moves from the cached system prompt into the conversation, injected at its two observable events — first turn (live-context) and each summarization (baked into the summary by `summarize_history`) — instead of being detected by a marker (refines ADR-0065, relates to ADR-0036, ADR-0039) — [adr-0082.md](adr-0082.md)
- **ADR-0086** — Split `workflow` out of `mandate` (project-doc reading, skills, working loop, verify gate, recovery); a pinned section list naming only `mandate` still receives both files (refines ADR-0035, ADR-0079) — [adr-0086.md](adr-0086.md)
- **ADR-0087** — `journal_mandate` carries the everyday write shapes inline (one activity line, one insight note); `core-journaling` owns structural work only (relates to ADR-0039, ADR-0069, ADR-0082) — [adr-0087.md](adr-0087.md)
- **ADR-0088** — Untrusted-data framing ships with the tool result (`read_file` header, raw `open_web_page` field), and injection refusal gains a non-interactive branch: refuse the directive, finish the real task — [adr-0088.md](adr-0088.md)
- **ADR-0089** — Home-level `AGENTS.md`/`CLAUDE.md` render under **User-Level Guidance** and are exempt from the mandatory project-doc read (refines ADR-0036) — [adr-0089.md](adr-0089.md)

### LLM extension surface
- **ADR-0041** — Tools as plain functions with PascalCase `__name__` — [adr-0041.md](adr-0041.md)
- **ADR-0042** — `tool_safe_async` + `[SYSTEM SUGGESTION]` error hints — [adr-0042.md](adr-0042.md)
- **ADR-0043** — Explicit tool-guidance registration + runtime filtering — [adr-0043.md](adr-0043.md)
- **ADR-0044** — Claude-compatible skills (`SKILL.md`/`.py`) + companion files — [adr-0044.md](adr-0044.md)
- **ADR-0045** — Subagent scope-clamp envelope + section inheritance — [adr-0045.md](adr-0045.md)
- **ADR-0090** — Delegation criteria are context-shaped (reads far more than it reports; or the parent's own context is the liability), not file-count-shaped; concurrent write fan-out shares one working tree and is called out as unsafe (relates to ADR-0045, ADR-0043) — [adr-0090.md](adr-0090.md)
- **ADR-0046** — `BufferedUI` + confirmation queue for concurrent agents — [adr-0046.md](adr-0046.md)
- **ADR-0047** — Lifecycle hooks (Claude-compatible) — [adr-0047.md](adr-0047.md)
- **ADR-0048** — MCP (Model Context Protocol) support — [adr-0048.md](adr-0048.md)
- **ADR-0049** — Tool capability tags (Primitive A) — [adr-0049.md](adr-0049.md)
- **ADR-0050** — Permission rulesets (Primitive B) — [adr-0050.md](adr-0050.md)
- **ADR-0051** — Plan mode (read-only discovery) — [adr-0051.md](adr-0051.md)
- **ADR-0052** — Tool-output truncation backstop — [adr-0052.md](adr-0052.md)
- **ADR-0053** — Dynamic, permission-filtered tool descriptions — [adr-0053.md](adr-0053.md)
- **ADR-0054** — Background subagents: inherit permissions and interrupt to ask — [adr-0054.md](adr-0054.md)
- **ADR-0055** — Approval precedence: permission policy → tool policy → yolo — [adr-0055.md](adr-0055.md)
- **ADR-0056** — Shell as primary execution tool, Bash as backward-compat alias — [adr-0056.md](adr-0056.md)
- **ADR-0057** — Post-todo-change progress visualization in the UI — [adr-0057.md](adr-0057.md)
- **ADR-0060** — `BaseUI` composed from concern mixins (shared-`self` contract) — [adr-0060.md](adr-0060.md)
- **ADR-0085** — Reserve the `Mixin` suffix for reusable mixins; single-host parts are named `<Owner><Aspect>` and `X/manager/manager.py` flattens to `X/manager.py` (refines ADR-0060, relates to ADR-0021) — [adr-0085.md](adr-0085.md)
- **ADR-0061** — Config-positioned custom prompt sections (registered provider or markdown file) — [adr-0061.md](adr-0061.md)
- **ADR-0062** — Intrinsic always-auto-approve for interaction tools (AskUserQuestion) — [adr-0062.md](adr-0062.md)
- **ADR-0063** — Opt-in two-layer filesystem sandbox (Python FS gate + OS shell wrapper) — [adr-0063.md](adr-0063.md)
- **ADR-0064** — Optional `ask_user_choice` protocol method with text fallback for arrow-key AskUserQuestion — [adr-0064.md](adr-0064.md)
- **ADR-0066** — Command hooks receive the event payload on stdin; `settings.json` is a hook source — [adr-0066.md](adr-0066.md)
- **ADR-0067** — Non-interactive runs resolve hard-ASK approvals deterministically (approve the plan gate, deny the rest) — [adr-0067.md](adr-0067.md)
- **ADR-0068** — Dead-code removal: `update_todo`/`clear_todos`, `from_yolo`, and 30+ unused symbols — [adr-0068.md](adr-0068.md)
- **ADR-0069** — Built-in LLM plugin split into governable core-skills / skills / agents — [adr-0069.md](adr-0069.md)
- **ADR-0070** — Fold `DelegateToAgentsParallel` into a `tasks=` arg on `DelegateToAgent` — [adr-0070.md](adr-0070.md)
- **ADR-0071** — Fold `ShellBackground` into a `background=True` parameter on `Shell`/`Bash` (supersedes ADR-0056 point 3) — [adr-0071.md](adr-0071.md)
- **ADR-0072** — Bounded `wait=`/`kill=` on background result-collection tools (refines ADR-0054) — [adr-0072.md](adr-0072.md)
- **ADR-0074** — Hook capability parity with Claude Code: tool gates via the single `call_tool` chokepoint, `Stop` block-to-continue + turn-extension, terminal `SessionEnd` (refines ADR-0047, ADR-0066) — [adr-0074.md](adr-0074.md)
- **ADR-0075** — Shift+Tab mode cycle (normal → auto-accept-edits → plan), reusing plan mode + selective yolo with a persistent status-bar badge (refines ADR-0051, ADR-0055) — [adr-0075.md](adr-0075.md)
- **ADR-0076** — Uniform `add_hook_factory` for task-level hook registration on both `LLMTask` and `LLMChatTask` (task-local-by-default); adds `LLMTask.history_manager` (relates to ADR-0061, ADR-0074) — [adr-0076.md](adr-0076.md)
- **ADR-0077** — Configurable semantic CLI color layer (`CLIStyleMixin`): physical helpers unchanged, semantic helpers (`stylize_muted`, `stylize_warning`, `stylize_error`, `stylize_highlight`, etc.) backed by `ZRB_CLI_COLOR_*`/`ZRB_CLI_STYLE_*` env vars — [adr-0077.md](adr-0077.md)
- **ADR-0078** — First-class `permissions` parameter/property on `LLMChatTask` (symmetric with `LLMTask`), forwarded to the inner task instead of smuggled through a hook factory + `current_permission_policy` ContextVar (refines ADR-0076) — [adr-0078.md](adr-0078.md)
- **ADR-0079** — Fold the skill catalogue into the `mandate` section via `{CORE_SKILLS}`/`{AVAILABLE_SKILLS}`/`{PREACTIVATED_SKILLS}` placeholders; drop the `claude_skills` section (refines ADR-0035, ADR-0069) — [adr-0079.md](adr-0079.md)
- **ADR-0080** — Mode cycle binds Shift+Tab only, with a Termux-detected (`CFG.IS_TERMUX`) plain-Tab fallback since Termux can't distinguish the two keys (refines ADR-0075) — [adr-0080.md](adr-0080.md)
- **ADR-0081** — Voice dictation via `/voice` command with push-to-talk keybinding, opt-in behind `ZRB_LLM_VOICE_ENABLED` — [adr-0081.md](adr-0081.md)
- **ADR-0083** — Model-adaptive prompt profiles: a profile-variant axis (`terse`/`explicit`) over the existing section composition; the profile is set by `ZRB_LLM_PROFILE` or a user-declared per-model registry — zrb does **not** guess capability from the model id (extends ADR-0061, relates to ADR-0035, ADR-0040) — [adr-0083.md](adr-0083.md)
- **ADR-0091** — A profile variant may add demonstrations but never add or re-phrase rules: `persona.explicit.md` is removed and `explicit` becomes `terse` plus worked examples, because added constraint mass degrades exactly the weaker models the profile targets (narrows ADR-0083) — [adr-0091.md](adr-0091.md)
- **ADR-0092** — A tool result reaches the model once, through `ToolReturn.return_value`; `content` stays unset because pydantic-ai delivers it as a *separate* `UserPromptPart`, which doubled every tool result and made each tool batch present as a new user turn — [adr-0092.md](adr-0092.md)
- **ADR-0093** — `auto` selects the `mini` profile from a *declared size* in the model id (a parameter count ≤14B, or a vendor small-tier label), never from a family name; makes ADR-0091's worked examples reach weak models by default (narrows ADR-0083) — [adr-0093.md](adr-0093.md)
- **ADR-0094** — Cross-section references are marked `<!--requires:section-->` and dropped at compose time when the target is not emitted, replacing prose "where present" hedges; all 63 section subsets are verified to compose without a dangling reference — [adr-0094.md](adr-0094.md)
- **ADR-0096** — A section may never cite another section — restate the rule in place, since `<!--requires:-->` cannot reach the Python-built `tool_guidance` — and `mandate` owns one six-rank Priority Order that ranks everything, so no section needs to describe its own standing (narrows ADR-0094, constrains ADR-0061) — [adr-0096.md](adr-0096.md)
- **ADR-0095** — The second prompt profile is renamed `explicit` → `mini`: after ADR-0091 stripped the directive re-phrasings it carries the same rules plus demonstrations, so the old name argued for the behaviour that ADR now forbids; a clean break with no alias, since both consumers fail loudly (renames ADR-0083) — [adr-0095.md](adr-0095.md)
- **ADR-0097** — The journal gets one master switch, `LLM_JOURNAL_ENABLED`, gated at `PromptManager.active_sections` so a single point reaches the section, the `<journal-index>` injection and both summarization paths; `core-journaling` is dropped per skill (built-in only) rather than by disabling `core_skills/` (extends ADR-0073, narrows ADR-0069) — [adr-0097.md](adr-0097.md)
- **ADR-0098** — A rule lives where it is enforced: runtime → tool docstring → prompt → skill. Collapses six rule sections to three (`persona`, `workflow`, `examples`); `mandate` folds into `workflow`, `git_mandate` is deleted because `bash_safe_command_policy` already enforces it (supersedes ADR-0043/ADR-0086 on the guidance registry, narrows ADR-0061) — [adr-0098.md](adr-0098.md)
- **ADR-0099** — Journal tools own the on-disk format; `core-journaling`, its templates, and `journal-lint.py` are deleted because the writers hold the linter's four invariants by construction (supersedes ADR-0097, extends ADR-0098) — [adr-0099.md](adr-0099.md)
- **ADR-0100** — `tool_guidance` and its four-host registry are deleted; per-tool rules live in docstrings, cross-tool policy in `workflow`, and `register_section` is the extension point (supersedes ADR-0043/ADR-0086 on the registry, extends ADR-0098) — [adr-0100.md](adr-0100.md)
- **ADR-0101** — Parallel tool calls are the prompt's unconditional default; `system_context` announces only the exception, because the affirmative branch was unreachable and gated the rule (amends ADR-0100) — [adr-0101.md](adr-0101.md)
- **ADR-0102** — Write-freshness, blind-edit-streak, and repeated-outcome rules move from the prompt into the tools themselves; the tool-policy chain cannot carry them because it never sees a result and does not run headless (applies ADR-0098) — [adr-0102.md](adr-0102.md)
🔖 [Documentation Home](../README.md)
