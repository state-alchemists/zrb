# Task model

How tasks are declared, wired, and run. See the [ADR index](README.md) for
format and tags.

---

## ADR-0006 — DAG dependencies via `>>` / `<<` operator overloading

**Status:** Accepted

**Context.** Pipelines need ordered, parallelizable dependencies declared in a
way that reads like data flow.

**Decision.** Tasks form a Directed Acyclic Graph. Dependencies are declared
with overloaded shift operators — `task_a >> task_b` ("A feeds B"), or the
reverse `<<` — or with the explicit `upstream=[...]` parameter. The session
traverses upstreams to find roots and runs independent branches concurrently.

**Consequences.** Pipelines are visually intuitive and self-documenting;
acyclicity prevents deadlocks; independent tasks parallelize. Cost: operator
overloading is a learned idiom; very large graphs are still defined in code.

**Alternatives rejected.** Method-call API (`b.add_upstream(a)` — verbose);
separate declarative DAG file (loses context, fights ADR-0001); linear
execution (no parallelism).

**Evidence.** **[DOCUMENTED]** `docs/core-concepts/tasks-and-lifecycle.md`
(both operator and parameter forms); `architecture.md` ("operator overloading
to make task dependency chaining visually intuitive"). **[INFERRED]**
`src/zrb/task/base/operators.py` (`handle_rshift`/`handle_lshift`),
`src/zrb/session/session.py` (`get_root_tasks` DFS).

---

## ADR-0007 — Specialized task classes over one generic type

**Status:** Accepted

**Context.** Shell commands, Python logic, AI agents, HTTP probes, and rsync all
share a lifecycle (deps, retries, readiness) but differ in execution.

**Decision.** A shared `BaseTask` owns the lifecycle; specialized subclasses
(`Task`, `CmdTask`, `LLMTask`, `HttpCheck`, `TcpCheck`, `Scheduler`,
`Scaffolder`, `RsyncTask`) override the async `_exec_action` hook.

**Consequences.** Each type validates and executes its own domain while sharing
dependency/retry/readiness semantics. Cost: more classes to learn than a single
parameterized task.

**Alternatives rejected.** One `Task(type="cmd"|"python"|"llm")` (less typesafe,
branchy); fully separate paradigms (no shared lifecycle).

**Evidence.** **[DOCUMENTED]** `docs/task-types/basic-tasks.md`,
`custom-tasks.md`. **[INFERRED]** `src/zrb/task/cmd_task.py`, `base_task.py`,
`scheduler.py`.

---

## ADR-0008 — `@make_task` decorator alongside direct instantiation

**Status:** Accepted

**Context.** Simple one-off tasks shouldn't require class instantiation
ceremony; reusable/lambda tasks sometimes need an object reference.

**Decision.** Offer both: `@make_task(...)` wraps a function into a `BaseTask`
(and auto-registers to a group if given), while direct `Task(...)`/`CmdTask(...)`
instantiation and `BaseTask` subclassing remain first-class.

**Consequences.** Low-ceremony common case, full control when needed. Cost: two
authoring styles to document.

**Alternatives rejected.** Decorator-only (no in-place object for chaining);
class-only (too verbose for simple cases).

**Evidence.** **[DOCUMENTED]** `docs/core-concepts/make-task.md` (comparison
table), `tasks-and-lifecycle.md`. **[INFERRED]** `src/zrb/task/make_task.py`
(delegates to `BaseTask`, auto-calls `group.add_task`).

---

## ADR-0009 — Inputs and Envs as first-class objects

**Status:** Accepted

**Context.** Tasks need typed parameters (interactive prompts, parsing,
validation, UI rendering) and environment wiring, inherited down the group tree.

**Decision.** Model inputs as typed classes (`StrInput`, `IntInput`,
`BoolInput`, `OptionInput`, `PasswordInput`, …) and envs as `Env`, `EnvMap`,
`EnvFile`. Each knows how to prompt, parse, default, and update the context;
both inherit recursively through the task graph.

**Consequences.** Type-specific validation, CLI prompting, and web-form
rendering come from one definition; inheritance avoids repetition. Cost: more
object types than bare strings/dicts.

**Alternatives rejected.** Bare strings/dicts (no typing/prompting/inheritance);
one generic `Parameter` (no type-specific behavior).

**Evidence.** **[DOCUMENTED]** `docs/core-concepts/inputs.md`,
`environments.md`. **[INFERRED]** `src/zrb/input/`, `src/zrb/env/`.

---

## ADR-0010 — `zrb_init.py` hierarchical discovery + explicit registration

**Status:** Accepted

**Context.** Tasks must be discoverable per-project yet shareable across a
directory tree, without magic.

**Decision.** zrb loads `zrb_init.py` files found from the cwd up to home
(configurable via `ZRB_INIT_FILE_NAME`/`ZRB_INIT_SCRIPTS`/`ZRB_INIT_MODULES`).
Tasks become available only by explicit registration (`cli.add_task`,
`group.add_task`, or `@make_task(group=...)`) — never by name introspection.

**Consequences.** Parent-directory tasks cascade to subdirectories (project +
global layering); nothing runs unless explicitly registered. Cost: users must
register tasks (no zero-config auto-discovery).

**Alternatives rejected.** Function-name introspection (too implicit);
dedicated task directory (less flexible than hierarchical discovery).

**Evidence.** **[DOCUMENTED]** `docs/core-concepts/tasks-and-lifecycle.md`
(recursive discovery + inheritance), `docs/configuration/env-vars.md`,
`docs/changelog-v1.md` (parent-directory loading).

---

## ADR-0011 — Retry, fallback, and successor as *tasks*, not exception handlers

**Status:** Accepted

**Context.** Recovery logic (alert, rollback, cleanup) is itself automation and
should compose with the rest of the graph.

**Decision.** A task declares `retries`/`retry_period`; on permanent failure its
`fallback` tasks run; on success its `successor` tasks run. Fallbacks/successors
are tasks in the DAG, not try/except blocks.

**Consequences.** Recovery is declarative, reusable, and visible in the graph.
Cost: recovery flows are modeled as tasks even when a small inline handler would
do.

**Alternatives rejected.** Inline try/except (couples recovery to the action);
auto-fallback on first failure (too aggressive); no fallback concept (breaks
error pipelines).

**Evidence.** **[DOCUMENTED]** `docs/core-concepts/tasks-and-lifecycle.md`
("Fallbacks and Retries"). **[INFERRED]** `src/zrb/task/base_task.py`
(`retries`, `fallback`, `successor`), `base/execution.py` (retry loop).

---

## ADR-0012 — Readiness checks as concurrent, task-based probes

**Status:** Accepted

**Context.** Tasks that start long-running services never "return"; downstreams
must proceed when the service is *ready*, not when the action *completes*.

**Decision.** A task may declare `readiness_check` tasks (e.g., `HttpCheck`,
`TcpCheck`). The action runs as a deferred background coroutine while the checks
poll; once checks pass, the task is "ready" and downstreams proceed.
`monitor_readiness=True` keeps probing and restarts the action on failure.

**Consequences.** Server-style tasks integrate into the DAG; downstreams don't
block on never-ending actions; crashes can trigger restarts. Cost: an extra
deferred-coroutine execution path and timing parameters to tune.

**Alternatives rejected.** Await action completion (never returns for daemons);
inline sleep/retry (couples waiting to the action); task-level timeout only
(no flexible probing).

**Evidence.** **[DOCUMENTED]** `docs/task-types/readiness-checks.md`,
`docs/core-concepts/make-task.md`. **[INFERRED]**
`src/zrb/task/base/execution.py` (`execute_action_until_ready`),
`base/monitoring.py`, `session.py` (`defer_action`/`wait_deferred`).

---

## ADR-0013 — `execute_condition` skips (not branches or exceptions)

**Status:** Accepted

**Context.** Pipelines need conditional steps (e.g., "deploy only in prod")
without imperative branching or abusing exceptions for control flow.

**Decision.** Each task has `execute_condition` (bool | f-string | callable). If
false, the task is *skipped* — its action doesn't run, but it unblocks
downstreams gracefully (no push to XCom, no fallback trigger).

**Consequences.** Conditional pipelines without branch nodes; skipped ≠ failed.
Cost: skip semantics (unblocks downstreams) must be understood.

**Alternatives rejected.** Branch/if-else task nodes (imperative, complicates the
DAG); exceptions to signal skip (exceptions are for errors).

**Evidence.** **[DOCUMENTED]** `docs/core-concepts/tasks-and-lifecycle.md`
("Conditional Execution"). **[INFERRED]** `src/zrb/task/base_task.py`.

---

## ADR-0014 — Triggers and Scheduler as long-running daemon tasks

**Status:** Accepted

**Context.** Reactive (file/webhook/queue) and time-based (cron) automation need
to run indefinitely and fire work when conditions are met.

**Decision.** `BaseTrigger` runs an infinite loop and pushes to an exchange XCom
that fans out to a `Callback` task; `Scheduler` extends it to push on cron
matches. Each firing runs the callback in an isolated sub-session.

**Consequences.** Event- and time-driven automation reuse the task engine and
XCom. Cost: daemon tasks run in the foreground (stopped via `Ctrl+C`); not a
managed background service.

**Alternatives rejected.** External cron/systemd (couples to OS, harder to
test); polling in user code (verbose, loses orchestration); blocking listeners
(freeze the loop).

**Evidence.** **[DOCUMENTED]** `docs/task-types/triggers-and-schedulers.md`.
**[INFERRED]** `src/zrb/task/base_trigger.py`, `scheduler.py`.

---

## ADR-0015 — Explicit task lifecycle state machine

**Status:** Accepted

**Context.** Fallback/successor triggering, downstream gating, and observability
need an unambiguous notion of where a task is in its life.

**Decision.** Track explicit states (started, ready, completed, skipped, failed,
permanently_failed, terminated) with a timestamped history. Downstreams run only
when upstreams are completed or skipped.

**Consequences.** Deterministic transitions, auditable history, correct
fallback/successor routing. Cost: more bookkeeping than boolean flags.

**Alternatives rejected.** Exception-driven control flow (lost in async stacks);
boolean flags (invalid combinations); assume-success (runs successors on
failure).

**Evidence.** **[DOCUMENTED]** `docs/core-concepts/tasks-and-lifecycle.md`
(lifecycle diagram). **[INFERRED]** `src/zrb/task_status/task_status.py`,
`session.py` (`is_allowed_to_run`).

---

## ADR-0016 — Capture declaration file/line for error attribution

**Status:** Accepted

**Context.** In deep async stacks, a failing task's traceback points at engine
internals, not at the user's task definition.

**Decision.** `BaseTask.__init__` captures the file and line where the task was
declared (via `inspect`) and annotates exceptions with it.

**Consequences.** Errors point the user straight at the offending definition.
Cost: one stack-frame capture per task construction (negligible).

**Alternatives rejected.** Runtime stack parsing (expensive, fragile); generic
error messages (unhelpful).

**Evidence.** **[DOCUMENTED]** `docs/advanced-topics/architecture.md`
("Developer-Centric Error Tracking"). **[INFERRED]** `src/zrb/task/base_task.py`.

---

## ADR-0017 — Re-raise cancellation (`CancelledError`) after cleanup

**Status:** Accepted

**Context.** `Ctrl+C` and task cancellation must tear the event loop down
cleanly without leaving tasks in inconsistent states.

**Decision.** Catch `(asyncio.CancelledError, KeyboardInterrupt, GeneratorExit)`
*separately* from normal exceptions: mark the task failed, then **re-raise** so
the loop unwinds; only non-cancellation exceptions feed the retry/fallback path.

**Consequences.** Responsive, clean shutdown; no zombie "running" tasks. Cost:
every execution layer must follow the catch-separately-and-re-raise discipline.

**Alternatives rejected.** Broad `except Exception` (swallows cancellation);
ignoring cancellation (inconsistent state, confusing logs).

**Evidence.** **[DOCUMENTED]** `docs/advanced-topics/architecture.md` ("Handling
Asynchronous Cancellation"). **[INFERRED]** `src/zrb/task/base/lifecycle.py`,
`base/execution.py`.
