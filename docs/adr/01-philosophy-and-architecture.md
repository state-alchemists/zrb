# Philosophy & architecture

The cross-cutting decisions that everything else inherits. See the
[ADR index](README.md) for the format and tag conventions.

---

## ADR-0001 — Pure-Python task definitions, no YAML/DSL

**Status:** Accepted (defining choice of v2; v1 was YAML-driven)

**Context.** Automation tools traditionally describe pipelines in YAML/JSON
(Ansible, GitHub Actions, GitLab CI, Airflow). zrb v1 itself was YAML-driven.
Declarative configs inevitably reinvent programming constructs — loops,
conditionals, string interpolation — badly.

**Decision.** Tasks are defined exclusively in pure Python: class instances
(`CmdTask(...)`, `Task(...)`), the `@make_task` decorator, or `BaseTask`
subclasses. No YAML, JSON, or custom DSL for task definitions.

**Consequences.** Users get type checking, linting, IDE completion, and the
whole PyPI ecosystem for free. Cost: authoring requires Python literacy, and
there is no language-agnostic config format.

**Alternatives rejected.** YAML/JSON declarative configs (reinvent programming
poorly); a custom DSL (parser burden, no tooling); implicit discovery by naming
convention (too magical).

**Evidence.** **[DOCUMENTED]** `docs/advanced-topics/architecture.md`: "Zrb
explicitly rejects YAML, JSON, or custom Domain Specific Languages (DSLs)…
YAML pipelines often reinvent programming constructs poorly… By using pure
Python, users get type safety, linting, code completion, and the entire PyPI
ecosystem out of the box." **[DOCUMENTED]** README "Why Choose Zrb?": "🐍 Pure
Python: … No complex DSLs or YAML configurations to learn." Implementation:
`src/zrb/task/make_task.py`; v1→v2 shift visible in `docs/changelog-v1.md` vs
`docs/changelog-v2.md`.

---

## ADR-0002 — Program against `Any*` interfaces, not concrete types

**Status:** Accepted

**Context.** The engine and runners must handle `Task`, `CmdTask`, `LLMTask`,
and arbitrary user subclasses uniformly, and stay refactorable.

**Decision.** Define abstract interfaces (`AnyTask`, `AnyGroup`, `AnyContext`,
`AnySession`, …) and program the engine/runners against those, never the
concrete classes. Concrete types are imported only where objects are
constructed.

**Consequences.** Total decoupling between engine and task implementations;
tests mock the interface; users inject custom implementations. Cost: an extra
abstraction layer and the discipline to keep interfaces honest.

**Alternatives rejected.** Concrete types everywhere (couples internals to the
public API); pure duck typing (less discoverable, weaker IDE support).

**Evidence.** **[DOCUMENTED]** `docs/advanced-topics/architecture.md` ("Interfaces
Everywhere (The `Any*` Pattern) … Always program against the `Any` interface,
not the concrete implementation."). Files: `src/zrb/task/any_task.py`,
`src/zrb/group/any_group.py`, `src/zrb/context/any_context.py`.

---

## ADR-0003 — Async-first execution engine (`asyncio`)

**Status:** Accepted

**Context.** Automation spends most of its time waiting — on services,
processes, HTTP, LLM streams. Threads bring GIL contention and harder
cancellation.

**Decision.** Build the whole engine on `asyncio`. The core is `async_run()`;
the synchronous `run()` is a thin wrapper that spins an event loop. Independent
tasks run concurrently via `asyncio.gather()`.

**Consequences.** Massive I/O concurrency without thread overhead; clean
`Ctrl+C` propagation via `CancelledError`. Cost: all task actions live in async
code paths, and blocking calls must be avoided or offloaded.

**Alternatives rejected.** Threading (GIL, harder state reasoning); synchronous
blocking (hangs the CLI on long waits); callback/reactive style (less Pythonic).

**Evidence.** **[DOCUMENTED]** `docs/advanced-topics/architecture.md`
("Asynchronous First … `asyncio` allows massive concurrency without the overhead
of threads."). Files: `src/zrb/task/base/execution.py`, `base/lifecycle.py`.

---

## ADR-0004 — Ambient state via `ContextVars`, not threaded arguments

**Status:** Accepted

**Context.** Execution nests deeply: runner → task → action → agent → tool →
sub-agent. Threading state (UI, session, logger, yolo, approval channel) through
every signature explodes APIs.

**Decision.** Carry ambient state in `contextvars.ContextVar`s, set with the
RAII pattern (`token = var.set(...)` / `var.reset(token)`) and read on demand.
A canonical registry lives in `src/zrb/contextvars.py`. `asyncio` propagates
context to child coroutines automatically (PEP 567).

**Consequences.** Clean signatures; sub-agents inherit parent state for free;
scoped resets prevent leaks. Cost: state is implicit (must consult the registry
to know what's in scope), and writes must be carefully scoped.

**Alternatives rejected.** Threading args everywhere (signature explosion);
thread-locals (incompatible with asyncio); global mutable state (unsafe,
no cleanup).

**Evidence.** **[DOCUMENTED]** `docs/advanced-topics/architecture.md` ("Implicit
State via `ContextVars`"); `src/zrb/contextvars.py` (registry, 10 vars across
four layers); `docs/advanced-topics/maintainer-guide.md` ("Context Propagation
Internals"). See also ADR-0018.

---

## ADR-0005 — Deferred f-string/Jinja rendering at execution time

**Status:** Accepted

**Context.** Task parameters (`cmd`, paths, messages, input defaults) often
depend on inputs, env, or upstream XCom values not known at definition time.

**Decision.** String properties may be plain strings, f-strings referencing
`{ctx.input.x}` / `{ctx.env.Y}`, or Jinja templates; they are rendered via
`ctx.render(value)` immediately before use, never at definition time.

**Consequences.** One definition adapts to runtime inputs and pipes upstream
outputs in. Cost: a property is never trustworthy as a literal — code must
remember to render it before use (a documented footgun).

**Alternatives rejected.** Static strings only (inflexible); arbitrary Python
expressions inline (powerful but harder to audit; injection risk).

**Evidence.** **[DOCUMENTED]** `docs/advanced-topics/architecture.md` ("F-String
and Jinja Rendering … Never trust a string property as static. Pass it through
`ctx.render(...)` immediately before execution."). Used throughout README/docs
examples.
