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

Append to the relevant thematic file, take the next free `ADR-NNNN` number, and
add a row to the index below. One decision per record. If a new decision
reverses an old one, mark the old one **Superseded by ADR-NNNN** rather than
deleting it — the history is the point.

## Index

### Philosophy & architecture — [01-philosophy-and-architecture.md](01-philosophy-and-architecture.md)
- **ADR-0001** — Pure-Python task definitions, no YAML/DSL
- **ADR-0002** — Program against `Any*` interfaces, not concrete types
- **ADR-0003** — Async-first execution engine (`asyncio`)
- **ADR-0004** — Ambient state via `ContextVars`, not threaded arguments
- **ADR-0005** — Deferred f-string/Jinja rendering at execution time

### Task model — [02-task-model.md](02-task-model.md)
- **ADR-0006** — DAG dependencies via `>>` / `<<` operator overloading
- **ADR-0007** — Specialized task classes over one generic type
- **ADR-0008** — `@make_task` decorator alongside direct instantiation
- **ADR-0009** — Inputs and Envs as first-class objects
- **ADR-0010** — `zrb_init.py` hierarchical discovery + explicit registration
- **ADR-0011** — Retry, fallback, and successor as *tasks*, not exception handlers
- **ADR-0012** — Readiness checks as concurrent, task-based probes
- **ADR-0013** — `execute_condition` skips (not branches or exceptions)
- **ADR-0014** — Triggers and Scheduler as long-running daemon tasks
- **ADR-0015** — Explicit task lifecycle state machine
- **ADR-0016** — Capture declaration file/line for error attribution
- **ADR-0017** — Re-raise cancellation (`CancelledError`) after cleanup

### State & context — [03-state-and-context.md](03-state-and-context.md)
- **ADR-0018** — Three-tier context: SharedContext → Session → Context
- **ADR-0019** — XCom as per-task FIFO queues with callbacks
- **ADR-0020** — `DotDict` for attribute-style access to ctx data

### Configuration — [04-configuration.md](04-configuration.md)
- **ADR-0021** — `CFG` singleton composed from domain mixins, flat access
- **ADR-0022** — `EnvField` descriptor for env-backed config
- **ADR-0023** — Precedence: env var → default_factory → attribute default
- **ADR-0024** — Config reads `os.environ` only; `.env` is the task layer's job
- **ADR-0025** — `_ZRB_ENV_PREFIX` + `ROOT_GROUP_NAME` for white-labeling

### Runners & packaging — [05-runners-and-packaging.md](05-runners-and-packaging.md)
- **ADR-0026** — One task definition, multiple runners (CLI + Web)
- **ADR-0027** — FastAPI + Uvicorn for the web runner
- **ADR-0028** — Nested CLI groups (`zrb <group> <task>`)
- **ADR-0029** — Battery-included builtin tasks, toggleable
- **ADR-0030** — Plugin/skill/agent discovery from directories
- **ADR-0031** — Scaffolder for template-based code generation
- **ADR-0032** — Poetry, single distribution, lazy heavy imports
- **ADR-0033** — Test discipline: ≥90%, public-API-only, F-only lint

### LLM core — [06-llm-core.md](06-llm-core.md)
- **ADR-0034** — pydantic-ai as the agent framework
- **ADR-0035** — MECE prompt sections via middleware composition
- **ADR-0036** — Self-managed history + two-tier summarization
- **ADR-0037** — Stream-error classification + cascading retry
- **ADR-0038** — Model capability registry + provider constraints
- **ADR-0039** — Markdown journal (dir + index) for long-term memory
- **ADR-0040** — Provider-agnostic, multi-vendor LLM support
- **ADR-0058** — History summarizer between deferred-tool iterations must not orphan tool-call metadata
- **ADR-0059** — Degenerate model output must not corrupt the conversation: scoped placeholder + empty-completion guard

### LLM extension surface — [07-llm-extension.md](07-llm-extension.md)
- **ADR-0041** — Tools as plain functions with PascalCase `__name__`
- **ADR-0042** — `tool_safe_async` + `[SYSTEM SUGGESTION]` error hints
- **ADR-0043** — Explicit tool-guidance registration + runtime filtering
- **ADR-0044** — Claude-compatible skills (`SKILL.md`/`.py`) + companion files
- **ADR-0045** — Subagent scope-clamp envelope + section inheritance
- **ADR-0046** — `BufferedUI` + confirmation queue for concurrent agents
- **ADR-0047** — Lifecycle hooks (Claude-compatible)
- **ADR-0048** — MCP (Model Context Protocol) support
- **ADR-0049** — Tool capability tags (Primitive A)
- **ADR-0050** — Permission rulesets (Primitive B)
- **ADR-0051** — Plan mode (read-only discovery)
- **ADR-0052** — Tool-output truncation backstop
- **ADR-0053** — Dynamic, permission-filtered tool descriptions
- **ADR-0054** — Background subagents: inherit permissions and interrupt to ask
- **ADR-0055** — Approval precedence: permission policy → tool policy → yolo
- **ADR-0056** — Shell as primary execution tool, Bash as backward-compat alias
- **ADR-0057** — Post-todo-change progress visualization in the UI
- **ADR-0060** — `BaseUI` composed from concern mixins (shared-`self` contract)
- **ADR-0061** — Config-positioned custom prompt sections (registered provider or markdown file)
- **ADR-0062** — Intrinsic always-auto-approve for interaction tools (AskUserQuestion)
- **ADR-0063** — Opt-in two-layer filesystem sandbox (Python FS gate + OS shell wrapper)
