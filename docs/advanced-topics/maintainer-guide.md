🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > Maintainer Guide

# Maintainer Guide

This guide is for developers who contribute to or maintain the Zrb project itself. It outlines the project's architecture, conventions, and release process.

---

## Table of Contents

- [Publishing Zrb](#publishing-zrb)
- [Inspecting Import Performance](#inspecting-import-performance)
- [Profiling Zrb](#profiling-zrb)
- [Testing Strategies](#testing-strategies)
- [Evaluating the LLM Agent](#evaluating-and-improving-the-llm-agent)
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

To maintain and improve the quality of the Zrb LLM agent, the project uses a set of automated evaluation challenges located in the `llm-challenges/` directory.

> 💡 **See:** `llm-challenges/AGENTS.md` for full evaluation protocol instructions.

### Process Overview

| Step | Action |
|------|--------|
| 1. Execute | Run challenges for all model combinations |
| 2. Analyze | Review generated REPORT.md for failures |
| 3. Optimize | Refactor prompts or tools |
| 4. Verify | Re-run challenges to confirm improvements |

### Running Challenges

```bash
cd llm-challenges/

# Quick verification test
python runner.py --models openai:gpt-4o google-gla:gemini-1.5-pro --timeout 120 --verbose

# Full test suite
python runner.py --timeout 3600 --parallelism 12 --verbose --models <model-list>
```

### Analyzing Results

| Output | Location |
|--------|----------|
| Report | `llm-challenges/experiment/REPORT.md` |
| Results | `llm-challenges/experiment/results.json` |

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

Zrb uses Python's `contextvars.ContextVar` to thread execution state through async coroutines without explicit parameter passing. There are eight `ContextVar` instances across the codebase, split into three layers. The single source of truth is `src/zrb/contextvars.py` (a re-export index); update this section whenever you add, remove, or rename a `ContextVar`.

### The Three Layers

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

All four are set at the start of `run_agent()` and reset in its `finally` block.

**Layer 3 — Tool ambient state** (`src/zrb/llm/tool/worktree.py`, `src/zrb/llm/tool/plan.py`, `src/zrb/llm/tool/ask.py`):

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
| 1 | `filter_nil_content` | `None`/`""` content in any part type (replaced with `"(empty)"`, or `"null"` for `ToolReturnPart`); injects `TextPart("(tool call)")` in `ModelResponse` when no text part exists but tool calls do |
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

The handler sits **last** in the retry chain in `handle_stream_error`, so it only fires when all other handlers (transient, prompt-too-long, missing-reasoning, invalid-tool-call) have given up. This guarantees that the existing one-shot DeepSeek path fires first and the nuclear option is truly a last resort.

### File Map

| File | Responsibility |
|------|---------------|
| `src/zrb/llm/agent/run/history_utils.py` | `sanitize_history()`, `filter_nil_content()`, `strip_thinking_parts()`, `strip_to_text_only()` |
| `src/zrb/llm/message.py` | `sanitize_orphaned_tool_calls()`, `ensure_alternating_roles()`, `validate_tool_pair_integrity()` |
| `src/zrb/llm/agent/run/openai_patch.py` | Monkey-patch for `content: null` serialization |
| `src/zrb/llm/agent/run/error_classifier.py` | `is_missing_reasoning_content_error()`, `is_opaque_validation_error()`, `is_invalid_tool_call_error()` |
| `src/zrb/llm/agent/run/retry_loop.py` | Retry decisions including `strip_thinking_parts` and the opaque-400 fallback |
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
| Run LLM challenges | `python runner.py --models <list> --verbose` |

---