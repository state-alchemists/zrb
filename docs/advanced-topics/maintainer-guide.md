🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > Maintainer Guide

# Maintainer Guide

This guide is for developers who contribute to or maintain the Zrb project itself. It outlines the project's architecture, conventions, and release process.

---

## Table of Contents

- [Publishing Zrb](#publishing-zrb)
- [Changelog](#changelog)
- [Inspecting Import Performance](#inspecting-import-performance)
- [Profiling Zrb](#profiling-zrb)
- [Testing Strategies](#testing-strategies)
- [Evaluating the LLM Agent](#evaluating-and-improving-the-llm-agent)
  - [One-on-One LLM Session](#one-on-one-llm-session)
- [Architecture & Philosophy](#architecture--philosophy)
- [Context Propagation Internals](#context-propagation-internals)
- [LLM History Sanitization Layer](#llm-history-sanitization-layer)
- [Quick Reference](#quick-reference)

> 💡 **First time tracing a chat request?** Start with [LLM Chat Request Lifecycle](./llm-chat-lifecycle.md) — it walks `zrb llm chat "..."` from CLI to UI streaming, with file paths at each step. This guide goes deeper on the internals; that one stitches them together.

---

## Publishing Zrb

To publish Zrb, you need a PyPI account and an API token.

### Prerequisites

| Platform | URL |
|----------|-----|
| PyPI | https://pypi.org/ |
| TestPyPI | https://test.pypi.org/ |

### Configuration

```bash
poetry config pypi-token.pypi <your-api-token>
```

### Publishing

```bash
source ./project.sh
docker login -U stalchmst
zrb publish all
```

### About `README.pypi.md`

`pyproject.toml` points at `README.pypi.md`, not `README.md`. The two READMEs differ only in their `docs/X` link format:

| File | Link format | Purpose |
|------|-------------|---------|
| `README.md` | Relative (`docs/foo.md`) | Single source of truth — works locally, on GitHub, and offline |
| `README.pypi.md` | Absolute, tag-pinned (`https://github.com/state-alchemists/zrb/blob/2.25.3/docs/foo.md`) | Generated artifact — packaged by Poetry, shown on the PyPI landing page |

`README.pypi.md` is **gitignored** and generated on demand by `scripts/build_pypi_readme.py`, which reads the version from `pyproject.toml` and rewrites every relative `docs/X` link to a tag-pinned GitHub URL. Tag-pinning means a user landing on `pypi.org/project/zrb/2.25.3/` always sees the docs as they existed at that release.

Two places already generate it for you:

- `source ./project.sh` — runs the script before `poetry install` during onboarding/reload, so a fresh clone has the file ready.
- `zrb publish pip` — runs the script before `poetry publish --build`, so each release ships with URLs pointing at the matching tag.

If you ever invoke `poetry build` / `poetry publish` directly (bypassing the `zrb publish pip` task), run `python scripts/build_pypi_readme.py` first or Poetry will fail with "readme not found."

> ⚠️ **Tag format.** Zrb's release tags are bare `major.minor.patch` (e.g. `2.25.3`), no `v` prefix. The script generates `/blob/2.25.3/...` accordingly — keep this convention if you ever need to rewrite the URL template.

---

## Changelog

The changelog lives in index and directory under `docs/`:

| Path | Scope |
|------|-------|
| `changelog.md` | Index page listing every minor version with links. |
| `changelog-v2/` | Directory of per-minor-version files (e.g. `2.38.0.md`, `2.35.0-2.35.3.md`). |
| `changelog-v1.md` | Archive of the 1.x line (and the 1.0.0 rewrite from 0.x). |

### Writing an entry

Each release is a `## <version> (<Month D, YYYY>)` heading followed by themed
bullets, with one blank line between entries:

```markdown
## 2.33.0 (June 6, 2026)

- **Feature: <Title>**:
  - <detail referencing a concrete symbol/path/env var>
- **Fix: <Title>**:
  - <detail>
```

Use `- **<Category>: <Title>**:` with nested `  - <detail>` sub-bullets.
Categories are free-form but conventionally `Feature` / `Improvement` / `Fix` /
`Reliability` / `Security` / `Refactor` / `Performance` / `Chore` /
`Documentation` / `Tests`. Write past-tense and factual, and anchor each point
to something locatable (`module.py`, `ClassName`, an env var, `ADR-NNNN`).

### Collapsing (compaction)

To keep the changelog readable as it grows, old entries are periodically
compacted. Each minor version has its own file under `changelog-v2/`. **Keep
only two entries per minor version** — the minor bump and its final revision —
producing this retained sequence:

```
x.y.0  →  x.y.z (latest revision of x.y)  →  x.y+1.0  →  x.y+1.w  →  …
```

Worked example (2.31–2.33):

```
changelog-v2/2.31.0.md  →  changelog-v2/2.32.0-2.32.2.md  →  changelog-v2/2.33.0-2.33.2.md
```

Here `2.31` had no patches (stays as `2.31.0.md`); `2.32` collapsed `2.32.1`
into `2.32.2` and its `2.32.0a1`–`b5` pre-releases into `2.32.0`; `2.33` (once
it ages out) collapses `2.33.1` into `2.33.2` and the file gets compacted to
`2.33.0-2.33.2.md`. **The newest minor stays at full per-patch detail** as an
uncollapsed file (e.g. `2.38.0.md`) until a later minor opens.

Rules for the surviving entries — they must not lose the dropped history:

- The kept **`x.y.z` (latest)** entry **summarizes the cumulative changes** of
  every dropped patch `x.y.1`–`x.y.z`, not merely its own.
- The kept **`x.y.0`** entry **absorbs its pre-releases** (`x.y.0a*`/`x.y.0b*`).
  The headline features usually land in the pre-release entries (the stable
  `.0` note often just says "consolidating the pre-release line below"), so
  dropping them without folding loses the real content.
- Mark a rolled-up entry with a one-line italic note directly under the heading:
  `_Cumulative summary of the X.Y.1–X.Y.Z patch line._`
- **Summarize, don't concatenate.** A 24-patch line becomes one
  release-note-sized entry grouped by theme; drop version-bump noise and
  test-only churn (one "expanded test coverage" mention suffices).
- Update `changelog.md` when renaming a file (e.g. `2.38.0.md` → `2.38.0-2.38.3.md`) so the link stays current.

Dropped content stays recoverable from git, so compaction is reversible — but
the goal is that the compacted file still conveys what happened across each
minor without it.

---

## Inspecting Import Performance

To inspect import performance and decide if a module should be lazy-loaded:

```bash
pip install benchmark-imports
python -m benchmark_imports zrb
```

---

## Profiling Zrb

To diagnose performance issues, generate a profile and visualize it.

### Generate Profile

```bash
python -m cProfile -o .cprofile.prof -m zrb --help
```

### Visualization Options

| Tool | Output | Command |
|------|--------|---------|
| `snakeviz` | Interactive HTML | `pip install snakeviz && snakeviz .cprofile.prof` |
| `flameprof` | Flame graph SVG | `pip install flameprof && flameprof .cprofile.prof > flamegraph.svg` |

---

## Testing Strategies

The test suite uses `pytest` fixtures and `unittest.mock.patch` (as decorators or context managers) to isolate components and ensure correctness.

Refer to existing tests in the `test/` directory for examples.

---

## Evaluating and Improving the LLM Agent

To maintain and improve the quality of the Zrb LLM agent, the project uses automated evaluation challenges hosted in a separate repository: [github.com/state-alchemists/llm-challenges](https://github.com/state-alchemists/llm-challenges).

> 💡 **See:** the [llm-challenges README](https://github.com/state-alchemists/llm-challenges) for full evaluation protocol instructions.

### Process Overview

| Step | Action |
|------|--------|
| 1. Execute | Run challenges for all model combinations |
| 2. Analyze | Review generated `REPORT.md` for failures |
| 3. Optimize | Refactor prompts or tools |
| 4. Verify | Re-run challenges to confirm improvements |

### Running Challenges

```bash
git clone https://github.com/state-alchemists/llm-challenges.git
cd llm-challenges/

# Quick verification test
python runner.py --models openai:gpt-4o google-gla:gemini-1.5-pro --timeout 120 --verbose

# Full test suite
python runner.py --timeout 3600 --parallelism 12 --verbose --models <model-list>
```

### Analyzing Results

| Output | Location |
|--------|----------|
| Report | `experiment/REPORT.md` |
| Results | `experiment/results.json` |

### One-on-One LLM Session

Beyond automated challenges, run a one-on-one session to understand how ergonomic the prompt feels to the LLM itself:

```bash
zrb chat "What is your honest analysis about your current system prompt/instruction. How helpful/effective/efficient is it? How easy/difficult is it for you to follow the instruction. Is that ergonomics? Give scores (1-10) for each aspect"
```

This surfaces friction that automated metrics miss — ask the model to rate helpfulness, effectiveness, efficiency, and ease of following the system prompt.

### Optimization Targets

| Target | Location |
|--------|----------|
| Prompts | `src/zrb/llm/prompt/markdown/` |
| Tools | `src/zrb/llm/tool/` |

---

## Architecture & Philosophy

To understand Zrb's core design decisions (such as the strict use of `asyncio`, the `Any*` decoupled interface pattern, and the underlying data flow), please read the dedicated **[Architecture, Philosophy, & Conventions](./architecture.md)** document.

---

## Context Propagation Internals

Zrb uses Python's `contextvars.ContextVar` to thread execution state through async coroutines without explicit parameter passing. There are eleven `ContextVar` instances across the codebase, split into five layers. The single source of truth is `src/zrb/contextvars.py` (a re-export index); update this section whenever you add, remove, or rename a `ContextVar`.

### The Five Layers

**Layer 1 — Task execution** (`src/zrb/context/any_context.py`):

```python
current_ctx: ContextVar[AnyContext | None] = ContextVar("current_ctx", default=None)
```

Holds the active `Context` for the currently executing task. Set at the start of `execute_task_action()`, reset in its `finally` block.

**Layer 2 — LLM agent execution** (`src/zrb/llm/agent/run/runner.py`, `src/zrb/llm/approval/approval_channel.py`):

| Variable | Type | Purpose |
|---|---|---|
| `current_ui` | `UIProtocol \| None` | Active UI for output and user interaction |
| `current_tool_confirmation` | `AnyToolConfirmation` | Tool approval policy |
| `current_yolo` | `bool` | Auto-approve all tool calls |
| `current_approval_channel` | `ApprovalChannel \| None` | Remote approval handler |
| `current_hook_manager` | `HookManager \| None` | Hook manager for the run; nested tools (e.g. delegate) fire SubagentStart/Stop on it |

All five are set at the start of `run_agent()` and reset in its `finally` block.

**Layer 3 — Permission state** (`src/zrb/llm/permission/state.py`):

| Variable | Type | Purpose |
|---|---|---|
| `current_permission_policy` | `PermissionPolicy \| None` | In-force tool ruleset (`None` = legacy yolo behavior). Set by `run_agent()` from the explicit arg or inherited from a parent run; reset in its `finally` block. |
| `current_agent_mode` | `AgentMode` | `DEFAULT` or `PLAN` (read-only). Set by the `EnterPlanMode` / `ExitPlanMode` tools; `PLAN` makes `get_effective_policy()` return the read-only `PLAN_MODE_POLICY`. |

**Layer 4 — Sandbox state** (`src/zrb/llm/sandbox/state.py`):

| Variable | Type | Purpose |
|---|---|---|
| `current_sandbox_policy` | `SandboxPolicy \| None` | In-force filesystem-containment policy (`None` = resolve from `CFG.LLM_SANDBOX_*`, which is disabled unless the deployment opted in). Set by `run_agent()` from the explicit arg or inherited from a parent run; reset in its `finally` block. Consumed by the `_sandbox_gate` in `agent/common.py` and the shell tools' OS-sandbox wrapper. |

**Layer 5 — Tool ambient state** (`src/zrb/llm/tool/worktree.py`, `src/zrb/llm/tool/plan.py`, `src/zrb/llm/tool/ask.py`):

| Variable | Type | Purpose |
|---|---|---|
| `active_worktree` | `str` | Path of the worktree the agent is currently operating in (set by `EnterWorktree`, cleared by `ExitWorktree`) |
| `_current_session` | `str` | Session id used by the todo tools so they default to the right conversation when called without an explicit `session=` |
| `interactive_mode` | `bool` | Whether the current chat session is interactive — gates `ask_user_question` so non-interactive runs short-circuit instead of blocking on stdin |

Set/cleared by their owning tool implementations rather than at a single entry point.

### The Scoping Pattern

Every `ContextVar` follows the same RAII-style pattern:

```python
token = current_ctx.set(ctx)
try:
    ...task body...
finally:
    current_ctx.reset(token)  # restores the previous value
```

The `reset(token)` call restores whatever value was in the variable before `set()` was called. This means nested calls (e.g. a sub-agent delegated from a parent agent) each get their own scope while still inheriting the parent's values at entry time.

### Inheritance Pattern

Agent context variables use a fallback pattern to enable parent→child inheritance:

```python
# run_agent.py — resolve effective value
effective_ui = ui_arg or current_ui.get()
effective_yolo = yolo or current_yolo.get()
```

If a child agent doesn't receive an explicit argument, it inherits from the context set by its parent. This allows YOLO mode, approval channels, and UI handles to flow naturally through nested agent calls.

### Why ContextVar (not Globals or Thread-locals)?

Zrb is fully asyncio-based. Thread-locals don't work with coroutines (multiple coroutines share a thread). A global dict keyed on task/session ID would work but adds lookup overhead and manual lifecycle management. `ContextVar` integrates directly with Python's asyncio scheduler:

- `asyncio.create_task()` automatically copies the current context to the new task (PEP 567).
- `asyncio.gather()` runs coroutines in-place, sharing the caller's context.
- Token-based `reset()` ensures correct cleanup even if exceptions occur.

### Known Inefficiency: `env` Dict Copy

Every time a `Context` object is created for a task (`context.py:25`), it copies the entire shared env dictionary:

```python
self._env = shared_ctx.env.copy()
```

This is O(n) in the number of env vars and happens once per task execution. For typical workloads (< 100 vars, dozens of tasks) it is not a bottleneck. If you are seeing memory pressure under large fan-out workloads (hundreds of concurrent tasks, large envs), this is the first place to look — a lazy/copy-on-write approach would eliminate redundant copies.

### Gotcha: `asyncio.create_task()` and Context Timing

At `execution.py:97`, a new asyncio task is created for action execution:

```python
action_coro = asyncio.create_task(run_async(execute_action_with_retry(task, session)))
```

Python copies the context at `create_task()` time. If the parent coroutine resets `current_ctx` before the new task is scheduled, the new task runs with the snapshot value from creation time — which may differ from the parent's current value. This is safe in practice because `execute_action_with_retry` re-establishes its own `current_ctx` scope, but it is worth keeping in mind if the execution model changes.

---

## LLM History Sanitization Layer

pydantic-ai passes the full conversation history to the provider on every turn. Several providers have subtle validation rules that cause them to reject a history that they themselves produced one turn earlier. This section explains those failure modes and the defensive layer Zrb adds on top of pydantic-ai.

### The Core Problem: Provider Inconsistency

When a model makes a tool call without accompanying text, the provider returns:

```json
{"role": "assistant", "content": null, "tool_calls": [...]}
```

This is valid per the OpenAI spec — `content: null` is explicitly allowed when `tool_calls` is set. pydantic-ai faithfully stores this as a `ModelResponse` with only a `ToolCallPart` (no `TextPart`).

On the next turn, pydantic-ai serializes the same history back:

```json
{"role": "assistant", "content": null, "tool_calls": [...]}
```

Some providers — including DeepSeek and several OpenAI-compatible APIs — **reject this identical structure** with:

```
Invalid assistant message: content or tool_calls must be set
```

The provider sent `content: null` and then refuses to accept `content: null` back. This is a provider-side inconsistency, not a pydantic-ai parsing bug or a corrupt API response.

The same pattern applies to thinking/reasoning models. DeepSeek R1 (and similar) emit `reasoning_content` alongside `content: null`. When that assistant message is echoed in a subsequent turn without the `reasoning_content` field, the provider returns:

```
Missing reasoning_content field
```

### Known Affected Providers

| Provider / Model | Symptom | Root Cause |
|---|---|---|
| DeepSeek V3.2+, V4 | `"content or tool_calls must be set"` | Rejects `content: null` in echoed history |
| DeepSeek R1 (pre pydantic-ai 1.90) | `"Missing reasoning_content field"` | `reasoning_content` dropped from echo |
| AWS Bedrock custom models (`zai.glm-5`, etc.) | `ValidationException` (empty message) | Strict message-structure validation; exact rule not disclosed by provider |
| Ollama (some models) | HTTP 400 with tool/function error | References non-existent tool name in response |

The `is_invalid_tool_call_error` classifier requires **both** an entity keyword (`"tool"`, `"function"`) **and** a problem keyword (`"unknown"`, `"invalid"`, `"not defined"`, `"not found"`) to trigger a retry. This dual-keyword check prevents false-positives on generic 400 errors like `"Invalid JSON body"` that contain a problem keyword but no entity keyword.

### The Orphaned Tool Pair Problem

History compression (triggered when the conversation exceeds the token limit) splits history into a "to summarize" slice and a "to keep" slice. The split point is chosen at a turn boundary, but a turn can span multiple messages: an assistant message that calls a tool and the following user message that contains the tool result.

If the split falls between a `ToolCallPart` (in the assistant `ModelResponse`) and its corresponding `ToolReturnPart` (in the subsequent `ModelRequest`), compression produces a "kept" slice that has a tool call with no matching return. Bedrock and several other providers validate this pairing and return `ValidationException`.

### The Sanitization Layer

Zrb applies `sanitize_history()` at three points:

1. **Before every `converse_stream` call** (`runner.py` — `_execution_loop`)
2. **On the result history** after a successful stream (`runner.py` — after `AgentRunResultEvent`)
3. **After history compression** on the kept slice (`history_summarizer.py` — `summarize_history`), which runs *all four sanitization steps* unconditionally to guarantee the returned history is provider-clean

`sanitize_history()` applies four steps in a fixed order so that each step's output is valid input for the next:

| Step | Function | What it fixes |
|------|----------|---------------|
| 1 | `filter_nil_content` | `None`/`""` content in any part type (replaced with `"(empty)"`, or `"null"` for `ToolReturnPart`); injects `TextPart("(tool call)")` only in a `ModelResponse` that has **neither** text **nor** tool calls. A tool-call-only response is left text-less (every provider accepts it; `openai_patch` omits the `content` field) — injecting a placeholder there leaks `"(tool call)"` into history, which weaker models then echo back as literal output. |
| 2 | `sanitize_orphaned_tool_calls` | Removes unmatched `ToolCallPart`/`ToolReturnPart` pairs; patches text-less messages left behind |
| 3 | Drop empty messages | Removes `ModelRequest`/`ModelResponse` objects that have no parts remaining after steps 1–2 |
| 4 | `ensure_alternating_roles` | Merges consecutive same-role messages by concatenating their `parts` lists (prevents back-to-back assistant or user messages) |

Step 2 is skipped when `allow_orphaned_tool_calls=True`. This flag must be set whenever `deferred_tool_results` is provided to `agent.run_stream_events()`: in that path, `ToolCallPart` entries in the history legitimately have no matching `ToolReturnPart` in the history — their returns are in `current_results`, not in the history list. Removing them would silently break tool execution.

```python
# runner.py — _execution_loop
current_history = sanitize_history(
    current_history,
    allow_orphaned_tool_calls=(current_results is not None),
)
```

Before applying fixes, `_detect_problems()` scans the history for invariant violations and logs each at DEBUG level. This covers nil content, text-less `ModelResponse` objects, consecutive same-role messages, and orphaned tool pairs. It has zero production overhead (DEBUG-only) but is invaluable when tracing the root cause of provider 400 errors.

### The OpenAI Serializer Patch

`filter_nil_content` fixes the problem at the `ModelMessage` object level (before serialization). There is a second, complementary fix at the serialization level: `openai_patch.py` monkey-patches `OpenAIChatModel._MapModelResponseContext._into_message_param`.

The upstream implementation always sets `content = None` when there is no text, which serializes to `"content": null` in JSON:

```python
# pydantic-ai upstream (≥ 1.90.0) — still present
if self.texts:
    message_param['content'] = '\n\n'.join(self.texts)
else:
    message_param['content'] = None   # sent as "content": null
```

The patch changes the `else` branch to only set `content` when there are *neither* `tool_calls` *nor* `thinkings`:

```python
# openai_patch.py
if self.texts:
    message_param['content'] = '\n\n'.join(self.texts)
elif not self.tool_calls and not self.thinkings:
    message_param['content'] = None   # only set null when nothing else is set
```

When `tool_calls` or `thinkings` are present, the `content` key is omitted from the serialized JSON entirely (not set to `null`). This is valid per the OpenAI API spec and accepted by all known providers.

The patch is applied once at import time (`runner.py` calls `patch_openai_model_response_serialization()` at module load). It fails silently if pydantic-ai's internal class structure changes, at which point `filter_nil_content` remains the fallback.

### The `strip_thinking_parts` Retry

For providers that reject history containing `ThinkingPart` entries even after the above sanitization (e.g. a DeepSeek model accessed via a non-DeepSeek provider that doesn't know how to serialize `reasoning_content`), the retry loop detects a specific 400 error matching `"missing reasoning_content"` or `"reasoning_content field"` (checked by `is_missing_reasoning_content_error`).

When detected, `strip_thinking_parts()` removes all `ThinkingPart` entries from every `ModelResponse` and retries. If stripping leaves a message with no parts (or no text part), a single `TextPart("(tool call)")` is injected to keep the message valid. This is a one-shot retry — it will not loop.

### The Generic Opaque-400 Fallback

The `strip_thinking_parts` retry still depends on the provider returning a specific (and knowable) error string. Some providers return opaque 400s with no usable message — GLM-5 on Bedrock returns `ValidationException` with an empty `Message` field; future providers will inevitably have their own opaque patterns.

Rather than catalog every variant, `retry_loop.py` has a catch-all that fires **once** for any unclassified HTTP 400:

1. It applies `strip_to_text_only()` to the message history. Each structured part is collapsed to its plain-text equivalent **inside its parent message's allowed type set**, because pydantic-ai's `_map_user_message` (`models/openai.py`) hits `assert_never` on any non-`{System,User,ToolReturn,Retry}PromptPart` it finds in a `ModelRequest`:
   - In `ModelResponse`: `BaseToolCallPart`/`BuiltinToolReturnPart`/`ThinkingPart` → `TextPart` with descriptive labels (e.g. `[Tool: deploy({"env":"prod"})]`, `[Result (deploy): started]`).
   - In `ModelRequest`: `ToolReturnPart` and tool-linked `RetryPromptPart` → `UserPromptPart` with the same kind of label (a `TextPart` inside a `ModelRequest` would crash the OpenAI mapper).
   Because both sides of every tool call/return pair are stripped in sympathy, no `tool_call_id` cross-reference survives — there is nothing left to orphan. Nil/empty content is replaced with `"."`. Large tool results are truncated to 500 chars.
2. It retries the model call with the sanitised history.

This is deliberately provider-agnostic. Text in the form `{"role": "user", "content": "..."}` / `{"role": "assistant", "content": "..."}` is the lowest common denominator that every text-generation provider accepts. The handler is gated on `current_message is not None` (it does not fire during tool-loop iterations with deferred results, where stripping structure could orphan tool call/return pairs).

The handler sits **last among the HTTP-400 handlers** in `handle_stream_error`, so it only fires when all other status-code handlers (transient, prompt-too-long, missing-reasoning, invalid-tool-call) have given up. This guarantees that the existing one-shot DeepSeek path fires first and the nuclear option is truly a last resort. (The deferred-mismatch handler below fires after it textually but is gated on a pydantic `UserError`, not an HTTP 400, so the two are mutually exclusive — ordering between them is immaterial.)

### The Deferred-Results-After-Summarization Recovery

The sanitization layer and `allow_orphaned_tool_calls` above protect against a tool **call/return pair** being split by compression. A different failure mode arises specifically *between* deferred-tool iterations: after a deferred tool is approved or denied, the loop re-enters `agent.run_stream_events()` with the resolved `DeferredToolResults`. Between iterations, `_apply_history_processors` runs the summarizer, which can compress the kept slice enough that the **entire `ModelResponse` whose `tool_calls` match `current_results`** is dropped. `allow_orphaned_tool_calls` does not help here — there is no orphaned *part* to preserve; the whole response carrying the tool calls is gone. pydantic-ai's `_handle_deferred_tool_results` then raises a `UserError` whose message contains *"does not contain any unprocessed tool calls"* (or *"does not contain a `ModelResponse`"*).

Two defenses cover this (see ADR-0058):

1. **Prevention (`runner.py`, `_execution_loop`)** — in the deferred-tool branch, `_apply_history_processors` is **skipped** when `current_results` still has pending `calls` or `approvals`; `current_history` is set directly to `run_history`. Processor effects are already applied in `_prepare_history` before the first stream call, and the summarizer still runs on every non-deferred iteration.

   ```python
   # runner.py — _execution_loop, deferred-tool branch
   if current_results and (
       getattr(current_results, "calls", None)
       or getattr(current_results, "approvals", None)
   ):
       current_history = run_history          # skip summarizer mid-deferral
   else:
       current_history = await _apply_history_processors(run_history, history_processors)
   ```

2. **Recovery (`retry_loop.py`, `handle_stream_error`)** — a one-shot handler (gated by `deferred_mismatch_retry_done`) catches the `UserError`, clears the stale `current_results` via `RetryOutcome.clear_results`, and retries so the model generates fresh tool calls. It hands back the **intact `run_history`** (not `None`) as `new_history`: the runner assigns `outcome.new_history` to `current_history` unconditionally and the next iteration feeds it straight into `sanitize_history`, which raises `TypeError` on `None`.

### The Empty-Completion Guard

The sanitization and retry layers above all handle *errors* (exceptions). A weak or overloaded provider has a quieter failure mode: the stream **succeeds** but the final turn carries no real content — zero output tokens, no tool call, and either empty text or just the `"(tool call)"` placeholder (injected by `filter_nil_content`, or echoed by a model that learned to imitate it). Left unguarded, that placeholder is surfaced to the user as the answer.

`_execution_loop` (`runner.py`) checks `_is_empty_completion(result_output)` after the stream, *after* the `DeferredToolRequests` branch (a deferred result is a legitimate tool-call outcome, never "empty") and *before* the `SESSION_END` hooks. `_is_empty_completion` returns `True` only for a **str** output that is blank or one of `_EMPTY_COMPLETION_MARKERS` (`"(tool call)"` and the bare `"(tool call"` imitation) — structured outputs are never caught.

On a hit it regenerates the turn rather than returning it: `_history_without_trailing_response(run_history)` drops the degenerate trailing `ModelResponse` (keeping any tool returns, so the deferred-resume case is handled too), `current_message`/`current_results` are reset to `None`, and the loop re-requests. This is bounded by `RetryState.max_empty_completion_retries` (default 2); once exhausted the loop raises a clear `RuntimeError` ("Model returned an empty response …") instead of looping forever or surfacing the placeholder. A legitimate answer is always non-empty prose, so this never rejects real output.

### File Map

| File | Responsibility |
|------|---------------|
| `src/zrb/llm/agent/run/history_utils.py` | `sanitize_history()`, `filter_nil_content()`, `strip_thinking_parts()`, `strip_to_text_only()` |
| `src/zrb/llm/message.py` | `sanitize_orphaned_tool_calls()`, `ensure_alternating_roles()`, `validate_tool_pair_integrity()` |
| `src/zrb/llm/agent/run/openai_patch.py` | Monkey-patch for `content: null` serialization |
| `src/zrb/llm/agent/run/error_classifier.py` | `is_missing_reasoning_content_error()`, `is_invalid_tool_call_error()` |
| `src/zrb/llm/agent/run/retry_loop.py` | Retry decisions including `strip_thinking_parts`, the opaque-400 fallback, and the deferred-mismatch recovery (`deferred_mismatch_retry_done` / `clear_results`) |
| `src/zrb/llm/agent/run/runner.py` | `_execution_loop`: skips history processors mid-deferral when `current_results` has pending calls/approvals |
| `src/zrb/llm/summarizer/history_summarizer.py` | Calls `sanitize_history()` on the kept slice after compression |

---

## Quick Reference

| Task | Command |
|------|---------|
| Publish | `zrb publish all` |
| Profile imports | `python -m benchmark_imports zrb` |
| Generate profile | `python -m cProfile -o .cprofile.prof -m zrb --help` |
| Visualize (snakeviz) | `snakeviz .cprofile.prof` |
| Visualize (flame) | `flameprof .cprofile.prof > flamegraph.svg` |
| Clone + run LLM challenges | `git clone https://github.com/state-alchemists/llm-challenges && cd llm-challenges && python runner.py --models <list> --verbose` |
| Run one-on-one LLM session | `zrb chat "What is your honest analysis about your current system prompt..."` |

---

🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > Maintainer Guide
