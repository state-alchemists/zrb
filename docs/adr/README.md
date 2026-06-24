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

### LLM extension surface
- **ADR-0041** — Tools as plain functions with PascalCase `__name__` — [adr-0041.md](adr-0041.md)
- **ADR-0042** — `tool_safe_async` + `[SYSTEM SUGGESTION]` error hints — [adr-0042.md](adr-0042.md)
- **ADR-0043** — Explicit tool-guidance registration + runtime filtering — [adr-0043.md](adr-0043.md)
- **ADR-0044** — Claude-compatible skills (`SKILL.md`/`.py`) + companion files — [adr-0044.md](adr-0044.md)
- **ADR-0045** — Subagent scope-clamp envelope + section inheritance — [adr-0045.md](adr-0045.md)
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

🔖 [Documentation Home](../README.md)
