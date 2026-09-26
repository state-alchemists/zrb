🔖 [Documentation Home](../../README.md) > [Technical Specs](./llm-context.md) > LLM History Sanitization

# LLM History Sanitization (Technical Specification)

pydantic-ai sends the full conversation history to the provider every turn, and several providers reject a history they themselves produced one turn earlier. This page covers those failure modes and the defensive layer Zrb adds on top of pydantic-ai.

---

## Table of Contents

- [The Core Problem: Provider Inconsistency](#the-core-problem-provider-inconsistency)
- [Known Affected Providers](#known-affected-providers)
- [The Orphaned Tool Pair Problem](#the-orphaned-tool-pair-problem)
- [The Sanitization Layer](#the-sanitization-layer)
- [The OpenAI Serializer Patch](#the-openai-serializer-patch)
- [The strip_thinking_parts Retry](#the-strip_thinking_parts-retry)
- [The Generic Opaque-400 Fallback](#the-generic-opaque-400-fallback)
- [The Deferred-Results-After-Summarization Recovery](#the-deferred-results-after-summarization-recovery)
- [The Empty-Completion Guard](#the-empty-completion-guard)
- [Re-checking a Mitigation Against a New pydantic-ai](#re-checking-a-mitigation-against-a-new-pydantic-ai)
- [File Map](#file-map)

---

## The Core Problem: Provider Inconsistency

For a tool call without text, the provider returns:

```json
{"role": "assistant", "content": null, "tool_calls": [...]}
```

This is valid per the OpenAI spec, and pydantic-ai stores it as a `ModelResponse` with only a `ToolCallPart` (no `TextPart`). Next turn, pydantic-ai serializes the same history back:

```json
{"role": "assistant", "content": null, "tool_calls": [...]}
```

Some providers — including DeepSeek and several OpenAI-compatible APIs — **reject this identical structure** with:

```
Invalid assistant message: content or tool_calls must be set
```

This is a provider-side inconsistency, not a pydantic-ai parsing bug or a corrupt response. Thinking models behave the same way: DeepSeek R1 (and similar) emit `reasoning_content` alongside `content: null`, and echoing that message without `reasoning_content` returns:

```
Missing reasoning_content field
```

## Known Affected Providers

| Provider / Model | Symptom | Root Cause |
|---|---|---|
| DeepSeek V3.2+, V4 | `"content or tool_calls must be set"` | Rejects `content: null` in echoed history |
| DeepSeek R1 (pre pydantic-ai 1.90) | `"Missing reasoning_content field"` | `reasoning_content` dropped from echo |
| AWS Bedrock custom models (`zai.glm-5`, etc.) | `ValidationException` (empty message) | Strict message-structure validation; exact rule not disclosed by provider |
| Ollama (some models) | HTTP 400 with tool/function error | References non-existent tool name in response |

The `is_invalid_tool_call_error` classifier retries only when the error has **both** an entity keyword (`"tool"`, `"function"`) **and** a problem keyword (`"unknown"`, `"invalid"`, `"not defined"`, `"not found"`), so a generic 400 like `"Invalid JSON body"` is not misclassified.

## The Orphaned Tool Pair Problem

History compression (when the conversation exceeds the token limit) splits history into "to summarize" and "to keep" slices at a turn boundary. But a turn can span an assistant message that calls a tool and the following user message holding its result. If the split falls between a `ToolCallPart` (in the `ModelResponse`) and its `ToolReturnPart` (in the next `ModelRequest`), the kept slice has a call with no return, and Bedrock and other providers return `ValidationException`.

## The Sanitization Layer

`sanitize_history()` runs at three points:

1. **Before every `converse_stream` call** (`runner.py` — `_execution_loop`)
2. **On the result history** after a successful stream (`runner.py` — after `AgentRunResultEvent`)
3. **After history compression** on the kept slice (`history_summarizer.py` — `summarize_history`), which runs *all four steps* unconditionally so the returned history is provider-clean

The steps run in a fixed order held in the `_SANITIZE_STEPS` tuple (`history_utils.py`), so reordering is a visible edit to that tuple. Each step's output must be valid input for the next:

| Step | Function | What it fixes |
|------|----------|---------------|
| 1 | `filter_nil_content` | `None`/`""` content in any part type (replaced with `"(empty)"`, or `"null"` for `ToolReturnPart`); injects `TextPart("(tool call)")` only in a `ModelResponse` with **neither** text **nor** tool calls. A tool-call-only response is left text-less (every provider accepts it; `openai_patch` omits the `content` field) — a placeholder there leaks `"(tool call)"` into history, which weaker models echo back as literal output. |
| 2 | `sanitize_orphaned_tool_calls` | Removes unmatched `ToolCallPart`/`ToolReturnPart` pairs; patches text-less messages left behind |
| 3 | Drop empty messages | Removes `ModelRequest`/`ModelResponse` objects with no parts left after steps 1–2 |
| 4 | `ensure_alternating_roles` | Merges consecutive same-role messages by concatenating their `parts` lists (prevents back-to-back assistant or user messages) |

Step 2 is skipped when `allow_orphaned_tool_calls=True`, which must be set whenever `deferred_tool_results` is passed to `agent.run_stream_events()`: there, history `ToolCallPart`s legitimately lack a `ToolReturnPart` because their returns are in `current_results`. Removing them would silently break tool execution.

```python
# runner.py — _execution_loop
cursor.begin_round(
    sanitize_history(
        cursor.history,
        allow_orphaned_tool_calls=(cursor.results is not None),
    )
)
```

Before and after the pipeline, `_detect_problems()` logs invariant violations at DEBUG: nil content, text-less `ModelResponse`s, consecutive same-role messages, and orphaned tool pairs. It costs nothing in production and helps trace provider 400s. A problem still present *after* the pipeline means the step order (or a step's contract) is wrong.

## The OpenAI Serializer Patch

`filter_nil_content` fixes the problem at the `ModelMessage` level; `openai_patch.py` adds a complementary serialization-level fix by monkey-patching `OpenAIChatModel._MapModelResponseContext._into_message_param`. Upstream sets `content = None` whenever there is no text, which serializes to `"content": null`:

```python
# pydantic-ai 2.27.0
if not self.texts and not self.tool_calls:
    return None                       # nothing to send: emit no message at all
...
if self.texts:
    message_param['content'] = '\n\n'.join(self.texts)
else:
    message_param['content'] = None   # sent as "content": null
```

The patch drops the `else`, so `content` is omitted when tool calls are present — valid per the OpenAI spec and accepted by all known providers. The first-line empty-response guard is upstream's, reproduced verbatim; returning a message there would be the same 400 in a different disguise.

No model profile flag disables the null, so the patch is still required as of 2.27.0. Upstream documents `_into_message_param` as an override hook, which makes the patch supportable even though its class is private. It is applied once at import (`runner.py` calls `patch_openai_model_response_serialization()` at module load); if pydantic-ai renames the target, the miss is logged at WARNING and `filter_nil_content` remains the fallback.

## The `strip_thinking_parts` Retry

Some providers reject history containing `ThinkingPart`s even after sanitization (e.g. a DeepSeek model behind a non-DeepSeek provider that can't serialize `reasoning_content`). The retry loop detects a 400 matching `"missing reasoning_content"` or `"reasoning_content field"` (`is_missing_reasoning_content_error`), then `strip_thinking_parts()` removes every `ThinkingPart` from every `ModelResponse` and retries once. A message left with no parts (or no text part) gets a single `TextPart("(tool call)")` to stay valid.

## The Generic Opaque-400 Fallback

Some providers return opaque 400s with no usable message (GLM-5 on Bedrock: `ValidationException` with an empty `Message`). Rather than catalog every variant, `retry_loop.py` has a catch-all that fires **once** for any unclassified HTTP 400:

1. It applies `strip_to_text_only()` to the history, collapsing each structured part to plain text **within its parent message's allowed part types** — pydantic-ai's `_map_user_message` (`models/openai.py`) hits `assert_never` on any non-`{System,User,ToolReturn,Retry}PromptPart` in a `ModelRequest`:
   - In `ModelResponse`: `BaseToolCallPart`/`BuiltinToolReturnPart`/`ThinkingPart` → `TextPart` with descriptive labels (e.g. `[Tool: deploy({"env":"prod"})]`, `[Result (deploy): started]`).
   - In `ModelRequest`: `ToolReturnPart` and tool-linked `RetryPromptPart` → `UserPromptPart` with the same kind of label (a `TextPart` inside a `ModelRequest` would crash the OpenAI mapper). Both sides of every call/return pair are stripped together, so no `tool_call_id` cross-reference survives to orphan. Nil/empty content becomes `"."`; tool results are truncated to 500 chars.
2. It retries with the sanitised history.

Plain `{"role": "user"|"assistant", "content": "..."}` text is the lowest common denominator every text-generation provider accepts. The handler is gated on `current_message is not None`, so it never fires during deferred-result tool-loop iterations, where stripping structure could orphan call/return pairs.

It sits **last among the HTTP-400 handlers** in `handle_stream_error`, after transient, prompt-too-long, missing-reasoning, and invalid-tool-call, so the DeepSeek path fires first and this stays a last resort. (The deferred-mismatch handler below comes after it textually but is gated on a pydantic `UserError`, not an HTTP 400, so their order is immaterial.)

## The Deferred-Results-After-Summarization Recovery

A separate failure arises *between* deferred-tool iterations. After a deferred tool is approved or denied, the loop re-enters `agent.run_stream_events()` with the resolved `DeferredToolResults`. If the summarizer ran in between, it could drop the **entire `ModelResponse` whose `tool_calls` match `current_results`** — no orphaned *part* for `allow_orphaned_tool_calls` to preserve. pydantic-ai's `_handle_deferred_tool_results` then raises a `UserError` containing *"does not contain any unprocessed tool calls"* (or *"does not contain a `ModelResponse`"*).

Two defenses cover this (see ADR-0040):

1. **Prevention (`runner.py`, `_execution_loop`)** — the deferred-tool branch calls `cursor.carry_forward()` (`turn_cursor.py`), the only place `TurnCursor.history` is set from `run_history`, never reapplying processors mid-deferral. It is unconditional because `_process_deferred_requests` populates `current_results.approvals` for every resolved call (approved, denied, or hook-blocked), so a "skip the summarizer?" guard would be true on every deferred iteration anyway. Processors already ran in `_prepare_history` before the first stream call, and the summarizer still runs on every non-deferred iteration.

   ```python
   # runner.py — _execution_loop, deferred-tool branch
   cursor.carry_forward()  # never reapply the summarizer mid-deferral
   ```

2. **Recovery (`retry_loop.py`, `handle_stream_error`)** — a one-shot handler (gated by `deferred_mismatch_retry_done`) catches the `UserError`, clears the stale `current_results` via `RetryOutcome.clear_results`, and retries so the model generates fresh tool calls. It returns the **intact `run_history`** (not `None`) as `new_history`, because the runner assigns `outcome.new_history` to `cursor.history` unconditionally and `sanitize_history` raises `TypeError` on `None`.

## The Empty-Completion Guard

A weak or overloaded provider can also **succeed** with no real content: zero output tokens, no tool call, and empty text or just the `"(tool call)"` placeholder (from `filter_nil_content`, or imitated by the model). Unguarded, that placeholder reaches the user as the answer.

`_execution_loop` (`runner.py`) checks `_is_empty_completion(result_output)` after the stream — *after* the `DeferredToolRequests` branch (a deferred result is a legitimate outcome) and *before* the `SESSION_END` hooks. It returns `True` only for a **str** output that is blank or one of `_EMPTY_COMPLETION_MARKERS` (`"(tool call)"` and the bare `"(tool call"` imitation); structured outputs are never caught.

On a hit, the loop regenerates the turn: `_history_without_trailing_response(run_history)` drops the degenerate trailing `ModelResponse` (keeping tool returns, so the deferred-resume case works), `current_message`/`current_results` reset to `None`, and it re-requests. This is bounded by `RetryState.max_empty_completion_retries` (default 2), after which it raises a clear `RuntimeError` ("Model returned an empty response …"). Real answers are non-empty prose, so it never rejects real output.

## Re-checking a Mitigation Against a New pydantic-ai

Each layer works around a *provider* bug, not a pydantic-ai one, so upgrades rarely retire any. Re-audit on a minor bump anyway: a dead layer keeps rewriting history for no reason.

Audited against **2.27.0**; every layer is still load-bearing:

| Layer | Verdict |
|---|---|
| `filter_nil_content` | Keep. Object-level guard against `None`/`""` content; nothing upstream normalizes this. |
| `openai_patch` | Keep. `_into_message_param` still writes `content = None` beside `tool_calls`, and no profile flag disables it. |
| `sanitize_orphaned_tool_calls` | Keep. The orphans are created by *zrb's* summarizer splitting a turn, so no upstream change can remove them. |
| `ensure_alternating_roles` | Keep. Same origin as above. |
| `strip_thinking_parts` retry | Keep. Error-triggered and free when it does not fire; the providers that reject echoed thinking still exist. |
| Opaque-400 text-only fallback | Keep. Deliberately provider-agnostic; upstream classifies transport errors, not provider quirks. |
| Deferred-mismatch recovery | Keep, and re-check the strings. It matches on `UserError` text raised by `_agent_graph`; both phrases are unchanged in 2.27.0. |
| Empty-completion guard | Keep. Guards a *successful* stream with no content — not an error path upstream ever sees. |

Two upstream changes were adopted: `ModelHTTPError` now carries `headers` and a parsed `retry_after`, which `get_retry_wait` reads before falling back to exponential backoff, and `known_model_names()` replaces unwrapping `KnownModelName.__value__` for `/model` completion.

## File Map

| File | Responsibility |
|------|---------------|
| `src/zrb/llm/agent/run/history_utils.py` | `sanitize_history()`, `_SANITIZE_STEPS`, `filter_nil_content()`, `strip_thinking_parts()`, `strip_to_text_only()`, `TurnPruneFloor` |
| `src/zrb/llm/agent/run/turn_cursor.py` | `TurnCursor` — the loop state `_execution_loop` threads across rounds; `carry_forward()` and `commit_round()` are the two invariants ADR-0040 depends on |
| `src/zrb/llm/message.py` | `sanitize_orphaned_tool_calls()`, `ensure_alternating_roles()`, `validate_tool_pair_integrity()` |
| `src/zrb/llm/agent/run/openai_patch.py` | Monkey-patch for `content: null` serialization |
| `src/zrb/llm/agent/run/error_classifier.py` | `is_missing_reasoning_content_error()`, `is_invalid_tool_call_error()` |
| `src/zrb/llm/agent/run/retry_loop.py` | Retry decisions including `strip_thinking_parts`, the opaque-400 fallback, and the deferred-mismatch recovery (`deferred_mismatch_retry_done` / `clear_results`) |
| `src/zrb/llm/agent/run/runner.py` | `_execution_loop`: never reapplies history processors mid-deferral |
| `src/zrb/llm/summarizer/history_summarizer.py` | Calls `sanitize_history()` on the kept slice after compression |

---

🔖 [Documentation Home](../../README.md) > [Technical Specs](./llm-context.md) > LLM History Sanitization
