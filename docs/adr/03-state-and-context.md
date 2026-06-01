# State & context

How execution state is isolated, shared, and accessed. See the
[ADR index](README.md) for format and tags. Closely related: ADR-0004
(ContextVars), ADR-0005 (deferred rendering).

---

## ADR-0018 — Three-tier context: SharedContext → Session → Context

**Status:** Accepted

**Context.** A run needs both shared state (env, inputs, XCom, logs) and
per-task isolation (so one task's env edits don't leak to siblings), and the
same task may run more than once in a run.

**Decision.** Three layers: **SharedContext** (run-wide immutable-ish shared
data), **Session** (mutable run state — statuses, upstream/downstream maps,
per-task contexts, deferred coroutines), and **Context** (per-task: attempt
count, task name, a *copy* of env, display color/icon). Actions receive their
own `ctx`.

**Consequences.** Tasks can't clobber each other's env/inputs; shared data lives
once in Session/SharedContext; clear ownership of mutable state. Cost: three
concepts to learn and keep distinct.

**Alternatives rejected.** Single global context (needs defensive copying
everywhere; unsafe); implicit-only access (hard to trace what's read).

**Evidence.** **[DOCUMENTED]** `docs/core-concepts/session-and-context.md`
(Session = factory floor, Context = workbench, XCom = conveyor belt).
**[INFERRED]** `src/zrb/session/session.py`, `src/zrb/context/context.py`,
`context/shared_context.py`.

---

## ADR-0019 — XCom as per-task FIFO queues with callbacks

**Status:** Accepted

**Context.** Tasks must exchange data without calling each other directly, and
triggers must react when data arrives.

**Decision.** Each task owns an `Xcom` (a `deque` subclass) in
`SharedContext.xcom[task_name]`. A task action's return value is auto-pushed to
its queue; downstreams `pop()`/`peek()` upstream queues. Push/pop callbacks let
`BaseTrigger` fire on data arrival. Accessible in templates via
`{ctx.xcom['task'].pop()}`.

**Consequences.** Decoupled, ordered, in-memory data flow with trigger hooks;
no external broker. Cost: in-process only (not durable, not cross-machine);
suited to small/medium payloads.

**Alternatives rejected.** Direct return values (break on skip/retry; can't
pipeline); shared globals (no ordering/deps); database/broker (heavyweight for
in-process flow).

**Evidence.** **[DOCUMENTED]** `docs/core-concepts/xcom-deep-dive.md`.
**[INFERRED]** `src/zrb/xcom/xcom.py`, `task/base/execution.py` (auto-push),
`base_trigger.py` (push callbacks).

---

## ADR-0020 — `DotDict` for attribute-style access to ctx data

**Status:** Accepted

**Context.** `ctx.env['DATABASE_URL']` is noisier than attribute access for the
common case, but dict semantics (iteration, dynamic keys) must remain.

**Decision.** `ctx.env`, `ctx.input`, and `ctx.xcom` use `DotDict`, a `dict`
subclass exposing attribute access (`ctx.env.DATABASE_URL`) while remaining a
full dict.

**Consequences.** Readable access and (often) editor autocomplete, with no loss
of dict behavior. Cost: attribute access can't autocomplete truly dynamic keys
and can shadow dict methods if keys collide.

**Alternatives rejected.** Plain dict + getters (verbose); namespace object
(harder to iterate/serialize); fixed attributes on Context (can't add keys
dynamically).

**Evidence.** **[DOCUMENTED]** `docs/advanced-topics/architecture.md`
("Ergonomic Data Access (`DotDict`)"). **[INFERRED]**
`src/zrb/dot_dict/dot_dict.py`, `src/zrb/context/context.py`.
