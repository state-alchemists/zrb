# LLM core

The agent engine: framework choice, prompt assembly, history, error recovery,
model awareness, memory. See the [ADR index](README.md) for format and tags.

---

## ADR-0034 — pydantic-ai as the agent framework

**Status:** Accepted

**Context.** `LLMTask`/`LLMChatTask` need a tool-calling agent loop with
streaming and multi-provider support. Building the loop from raw SDK calls means
reimplementing orchestration; heavyweight frameworks constrain the fine-grained
control zrb needs over approval, UI, and history.

**Decision.** Wrap `pydantic_ai.Agent` (created in `agent/common.py`). Tools are
type-annotated Python functions; the event stream drives zrb's UI and approval
flow; the provider abstraction gives vendor-agnosticism. zrb keeps pydantic-ai
thin enough to override behavior (history, retries) where needed.

**Consequences.** Async-native, structured tools, provider-agnostic, low
coupling. Cost: a dependency on pydantic-ai's model and the occasional need to
work around its internals (see ADR-0036).

**Alternatives rejected.** Raw SDK calls (reimplement the tool loop, large bug
surface); LangChain (heavy, opinionated callback model; awkward async control);
RAG-first frameworks (wrong problem domain).

**Evidence.** **[DOCUMENTED]** `docs/advanced-topics/architecture.md` ("agents
using pydantic-ai"), `AGENTS.md` ("create pydantic-ai agents internally"),
`src/zrb/llm/agent/common.py` (comments). **[INFERRED]** commits "WIP: use
pydantic ai" / "Fully use pydantic ai".

---

## ADR-0035 — MECE prompt sections via middleware composition

**Status:** Accepted

**Context.** A monolithic system prompt accretes duplicate and contradictory
rules and is hard to audit or extend.

**Decision.** `PromptManager` composes the system prompt from ordered,
single-concern sections (`persona → mandate → git_mandate → journal_mandate →
system_context → project_context → tool_guidance → claude_skills`) via a
chain-of-responsibility middleware. **Each section is MECE — one behavior lives
in exactly one section.** Order is overridable
(`ZRB_LLM_INCLUDE_SECTIONS`); sections may be static `.md` or dynamic
middleware that inspect the resolved model/tools at render time.

**Consequences.** A rule has exactly one home (easy to find, no contradictions);
sections are independently testable and swappable; dynamic sections inject
model-aware guidance at render time. Cost: contributors must place each rule in
the correct smallest-scope section.

**Alternatives rejected.** Free-form concatenation (duplication, conflicts);
single mega-prompt (can't share/override rules); nested hierarchy (overkill).

**Evidence.** **[DOCUMENTED]** `AGENTS.md` (LLM Prompt System, "Each section is
MECE"), `config/mixins/llm_prompt.py` (default order), `src/zrb/llm/prompt/
manager.py`, `prompt/markdown/*.md`.

---

## ADR-0036 — Self-managed history + two-tier summarization

**Status:** Accepted

**Context.** Conversations outgrow the context window, and pydantic-ai applies
history processors to a *shallow copy* it never writes back — so summaries done
its way are silently discarded.

**Decision.** zrb owns history. Processors are stored on the agent
(`_zrb_history_processors`) and applied by zrb itself before the first model
call and between tool-loop iterations, where it controls the history reference.
Summarization is two-tier: oversized individual tool results are compressed
(message summarizer), and when total tokens exceed a threshold the older portion
is condensed into a `<state_snapshot>` while recent turns are kept verbatim
(conversational summarizer). History is re-sanitized after compression.

**Consequences.** Summaries persist; long sessions stay within budget while
preserving recent fidelity. Cost: a parallel history pipeline zrb must maintain
against pydantic-ai's behavior.

**Alternatives rejected.** Rely on pydantic-ai processors (shallow-copy bug
discards them); naive truncation (loses decisions); no summarization (provider
rejects over-long history).

**Evidence.** **[DOCUMENTED]** `src/zrb/llm/agent/common.py` (comment on why
`history_processors` is omitted), `docs/advanced-topics/maintainer-guide.md`
(sanitization layer), `prompt/markdown/conversational_summarizer.md`,
`message_summarizer.md`. **[INFERRED]** `src/zrb/llm/summarizer/`.

---

## ADR-0037 — Stream-error classification + cascading retry

**Status:** Accepted

**Context.** Providers reject valid requests inconsistently — context-length
errors, malformed tool calls, missing `reasoning_content`, opaque Bedrock 400s.
A single retry strategy fails on most of these.

**Decision.** Classify stream errors and apply escalating, mostly one-shot
tactics: transient (429/5xx) → bounded exponential backoff; prompt-too-long →
drop the oldest turn (bounded, keep a minimum); invalid tool call → inject one
corrective system message; missing reasoning → strip thinking parts; opaque 400
→ collapse history to text-only. Surgical fixes, never "ask the model to fix it."

**Consequences.** Robust across provider quirks; no infinite loops (one-shot per
strategy); degrades gracefully to a text-only last resort that any provider
accepts. Cost: a classifier + retry matrix to maintain as providers change.

**Alternatives rejected.** Single fixed retry (same error repeats forever);
regenerate whole response (costly, may recur); fail immediately (loses session);
ask the user (blocks automation).

**Evidence.** **[DOCUMENTED]** `src/zrb/llm/agent/run/retry_loop.py`,
`error_classifier.py` (per-provider comments), `docs/advanced-topics/
maintainer-guide.md` (affected providers, opaque-400 fallback).

---

## ADR-0038 — Model capability registry + provider constraints

**Status:** Accepted

**Context.** Models diverge in capabilities (image/audio input, parallel tool
calls). Some OpenAI-compatible endpoints *ignore* `parallel_tool_calls=False`
and still malform parallel calls.

**Decision.** Maintain a per-model capability registry (name-pattern table +
user overrides; tri-state fields where `None` = unknown/pass-through). Apply
constraints two ways: at the provider level (`parallel_tool_calls=False` in
`model_settings`) and at the prompt level (a model-specific tool-guidance
section) — defense in depth for endpoints that ignore the flag.

**Consequences.** Known-bad models are handled at both layers; users register
private models without forking. Cost: a registry to keep current.

**Alternatives rejected.** No tracking (silent malformed calls, retry storms);
prompt-only (doesn't stop malformed emissions); per-call runtime discovery
(inconsistent, slow).

**Evidence.** **[DOCUMENTED]** `src/zrb/llm/util/capabilities.py`,
`src/zrb/llm/agent/common.py` (`_apply_capability_constraints`, two-layer
comment), `docs/advanced-topics/llm-integration.md` (Model Capabilities).

---

## ADR-0039 — Markdown journal (dir + index) for long-term memory

**Status:** Accepted (superseded the earlier single-JSON note store)

**Context.** Agent long-term memory needs to be human-readable, organizable, and
cheap on tokens (not everything belongs in every prompt).

**Decision.** Store memory as a hierarchical Markdown directory
(`ZRB_LLM_JOURNAL_DIR`). Only `index.md` is injected into the system prompt
(auto-created if missing); detailed notes are read on demand via tools
(`SearchJournal`). Placeholders like `{CFG_LLM_JOURNAL_DIR}` resolve at render
time.

**Consequences.** Organizable, editable, version-controllable memory; only the
index costs tokens every turn. Cost: the model must actively read deeper notes.

**Alternatives rejected.** Single JSON note file (flat, hard to grow); embed all
notes in the prompt (token waste); external DB (overkill, less portable).

**Evidence.** **[DOCUMENTED]** `docs/technical-specs/llm-context.md` (storage
mechanism), `src/zrb/llm/prompt/system_context.py` / `journal_mandate.md`.

---

## ADR-0040 — Provider-agnostic, multi-vendor LLM support

**Status:** Accepted

**Context.** Locking to one vendor risks cost, availability, and TOS exposure;
teams want to pick a model per workload.

**Decision.** Selection is by configuration (model string, base URL, API key),
resolved through pydantic-ai's provider abstraction. Each vendor SDK
(anthropic, openai, cohere, google-genai, xai, groq, bedrock, …) is an optional
extra, imported lazily.

**Consequences.** Switch providers by env var, no code change; cost optimization;
not beholden to one vendor's roadmap. Cost: must track capability quirks across
providers (ADR-0037, ADR-0038).

**Alternatives rejected.** Single-vendor lock-in (inflexible, risky); a bespoke
provider abstraction (duplicates pydantic-ai).

**Evidence.** **[DOCUMENTED]** `docs/configuration/llm-config.md`,
`docs/advanced-topics/llm-integration.md`, `pyproject.toml` (optional provider
extras). **[INFERRED]** `src/zrb/config/mixins/llm_core.py`.

---

## ADR-0058 — History summarizer between deferred-tool iterations must not orphan tool-call metadata

**Status:** Accepted

**Context.** After a deferred tool is approved or denied, the agent loop iterates:
it calls `_process_deferred_requests`, then re-enters
`agent.run_stream_events()` with the resolved `DeferredToolResults`. Between
these iterations, `_apply_history_processors` runs the summarizer, which can
compress old messages enough that the `ModelResponse` whose `tool_calls` match
`current_results` is dropped from `to_keep`. When `_handle_deferred_tool_results`
(pydantic-ai) next looks for the last `ModelResponse` with tool calls, it finds
none and raises `UserError("does not contain any unprocessed tool calls")`.

This error is not handled by any existing retry strategy, so it propagates to
`_handle_run_error`, which injects `[SYSTEM] Error occurred:` into history —
poisoning every subsequent task-level retry with the same corrupted state. The
result is an infinite retry death spiral.

**Decision.** Two defences, one tactical and one strategic:

1. **Fix A — `handle_stream_error` catch (retry_loop.py):** A new handler
   catches `UserError("does not contain any unprocessed tool calls"...)`
   before the final fallthrough to `should_retry=False`. It clears stale
   `current_results` via `RetryOutcome.clear_results` and returns
   `should_retry=True` together with `new_history=run_history` (the intact
   conversation history), allowing the model to generate fresh tool calls.
   Returning the intact history is load-bearing: the runner assigns
   `outcome.new_history` to `current_history` unconditionally, and the next
   loop iteration feeds it straight into `sanitize_history`, which raises
   `TypeError` on `None` — so a `None` here would convert the death spiral
   into a hard crash on the very path this handler exists to rescue. A
   one-shot gate (`deferred_mismatch_retry_done`) prevents re-entering this
   handler on a second retry of the same poisoned state.

2. **Fix B — suppress summarizer between iterations (runner.py):** A condition
   guard checks whether `current_results` has pending `calls` or `approvals`
   before calling `_apply_history_processors` in the deferred-tool branch of
   `_execution_loop`. When pending results exist, `current_history` is set
   directly to `run_history` without processor application. The summarizer
   still runs in `_prepare_history` before the first stream call and on all
   non-deferred iterations.

**Consequences.** The death spiral is broken at both the symptom (Fix A) and
root cause (Fix B). Fix A also serves as a safety net for any future scenario
where deferred-tool metadata and history are similarly mismatched. Cost: a
small complexity increment in the retry state machine and execution loop.

**Alternatives rejected.**
- Increase summarizer `to_keep` size — risks context-window overflow; only
  probabilistically avoids the race.
- Disable the summarizer entirely — undermines ADR-0036's compression benefit.
- Patch pydantic-ai's `_handle_deferred_tool_results` — vendor dependency;
  breaks on update.
- `history_processors` on every iteration — defeats the guard's purpose (Fix B
  *removes* a call).

**Evidence.** **[DOCUMENTED]** `src/zrb/llm/agent/run/retry_loop.py` (Fix A:
`deferred_mismatch_retry_done` flag, `clear_results`, UserError handler before
final return), `src/zrb/llm/agent/run/runner.py` (Fix B: pending-results guard
in the deferred-tool branch of `_execution_loop`),
`test/llm/agent/run/test_retry_loop.py`
(`test_handle_stream_error_deferred_mismatch*`,
`test_handle_stream_error_user_error_other_message`),
`test/llm/agent/run/test_runner.py`
(`test_run_agent_deferred_skips_processors_when_calls_pending`,
`test_run_agent_deferred_runs_processors_when_no_pending`,
`test_run_agent_deferred_mismatch_recovers_without_crash`).

---

## ADR-0059 — Degenerate model output must not corrupt the conversation: scoped placeholder + empty-completion guard

**Status:** Accepted

**Context.** Weak / overloaded models (observed: `deepseek-v4-flash` on ollama)
expose two coupled failure modes:

1. They emit assistant turns with **no text** — narration goes into a
   `ThinkingPart` and a tool call, leaving `content` empty. `filter_nil_content`
   injected a `TextPart("(tool call)")` whenever a `ModelResponse` had no text,
   *including* tool-call-bearing turns. That placeholder is stored in history,
   re-sent every turn, and the model **learns to imitate it** — emitting
   `"(tool call)"` (or the truncated `"(tool call"`) as literal output. (One
   production transcript: 29 placeholder turns, then 3 model-emitted imitations.)
2. Under load / context pressure the stream **succeeds** but returns an empty
   completion (zero output tokens, no tool call, no real text). The agent loop
   accepted it and surfaced the `"(tool call)"` placeholder to the user as the
   final answer.

The placeholder injection's own comment said it was for responses with "no text
**and** no tool calls" — but the code fired on "no text" alone, over-injecting.

**Decision.** Two scoped defenses:

1. **Scope the placeholder (`history_utils.py::filter_nil_content`).** Inject
   `TextPart("(tool call)")` only when a `ModelResponse` has **neither** text
   **nor** tool calls (the truly-empty turn providers reject). A tool-call-only
   turn is left text-less — every provider accepts it and `openai_patch` already
   omits the `content` field — so nothing imitable enters history. This aligns
   the code with its own documented intent.
2. **Empty-completion guard (`runner.py::_execution_loop`).** After the stream
   (post-`DeferredToolRequests`, pre-`SESSION_END`), `_is_empty_completion` flags
   a blank-or-placeholder **str** output. On a hit the turn is regenerated —
   `_history_without_trailing_response` drops the degenerate trailing
   `ModelResponse` (keeping tool returns, so the deferred-resume case works),
   results/message reset to `None` — bounded by
   `RetryState.max_empty_completion_retries` (default 2), then a clear
   `RuntimeError` rather than surfacing the placeholder or looping forever.

**Consequences.** The imitation feedback loop is cut at the source (1) and the
degenerate terminal output is never shown (2). A genuine answer is always
non-empty prose, so the guard never rejects real output; structured (non-str)
outputs and `DeferredToolRequests` are excluded by construction. Cost: one extra
post-stream check and a small retry counter.

**Alternatives rejected.**
- Keep injecting and make the placeholder "non-imitable" — fragile; any visible
  marker in history is imitable.
- Drop the placeholder entirely (even for text-less + tool-less turns) — those
  turns are genuinely rejected by Bedrock/OpenAI; the placeholder is still needed
  there.
- Surface the empty output as the answer — silent wrong result that also poisons
  the next turn's history.
- Treat empty completion as a stream error in `handle_stream_error` — it is not
  an exception; the stream succeeds, so it belongs in the runner loop.

**Evidence.** **[DOCUMENTED]** `src/zrb/llm/agent/run/history_utils.py`
(`filter_nil_content` `has_tool_call` guard),
`src/zrb/llm/agent/run/runner.py` (`_is_empty_completion`,
`_history_without_trailing_response`, `_EMPTY_COMPLETION_MARKERS`, the loop
guard), `src/zrb/llm/agent/run/retry_loop.py`
(`empty_completion_retry_count` / `max_empty_completion_retries`),
`docs/advanced-topics/maintainer-guide.md` (sanitization table row + "The
Empty-Completion Guard"). Tests: `test/llm/agent/run/test_history_utils.py`
(`test_filter_nil_content`,
`test_filter_nil_content_injects_placeholder_when_no_text_and_no_tool_call`,
`test_filter_nil_content_no_placeholder_for_tool_call_only`),
`test/llm/agent/run/test_runner.py`
(`test_run_agent_retries_empty_completion_then_succeeds`,
`test_run_agent_retries_tool_call_placeholder_leak`,
`test_run_agent_empty_completion_raises_after_retries`).
