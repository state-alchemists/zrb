🔖 [Documentation Home](../../README.md) > [Architecture](../README.md) > History & Compaction

# History & Compaction

> **Tier 3 · Peripheral flow** · Code: `src/zrb/llm/history_manager/` · Read first: [The LLM Turn](../1-spine/llm-turn.md)

History is what lets a conversation continue: the next turn, a resumed session, or a retry after a crash all start from the saved message list. This page covers how that list is loaded, shrunk when it outgrows the model's window, repaired before it is sent, and saved. The one idea to take away: the summary is not a side channel; it is a message inside the list, and that list is exactly what gets saved.

## Table of Contents

- [Design](#design)
  - [The problem](#the-problem)
  - [Principles](#principles)
  - [Invariants](#invariants)
- [Realization](#realization)
  - [The parts](#the-parts)
  - [How it runs](#how-it-runs)
  - [Variations](#variations)
  - [Change it here](#change-it-here)
- [See Also](#see-also)

## Design

### The problem

- **Conversations outgrow the context window.** Old messages must be shrunk, but the model still needs the decisions and the original goal they hold.
- **The list has structure a provider checks.** Every tool call needs its result, roles must alternate, and empty parts are rejected. Cutting the list in the wrong place, or saving a broken one, fails every later request.
- **A turn can die halfway.** A crash, an error or the user pressing Esc can stop a turn after tools already ran. If that work is not saved, the next turn repeats it blindly.
- **Writing the file is itself a risk.** A crash in the middle of a write must not destroy the whole conversation, and a second writer (another manager, an external edit) must not silently win over unsaved work.

### Principles

1. **The summary is part of the history, not beside it.** Compaction replaces the old part of the list with one restoration message, keeps the opening user goal word for word and the recent tail as a rendered-to-text copy (not resent as separate structured messages), and that new list is what gets saved. The next turn loads it like any other history. → [ADR-0041](../../adr/adr-0041.md)

2. **Shrink the cheapest thing first, and fail open.** First, an oversized tool result is summarized on its own. Only when the whole conversation is still over the threshold is the old part condensed into a state snapshot. If summarizing fails, the history goes through unchanged rather than failing the turn. → [ADR-0041](../../adr/adr-0041.md)

3. **Compact once per turn, before the first model call.** Between the rounds of one turn the list is carried forward as it is. Compacting again mid-turn could drop the message that holds an approved tool call. → [ADR-0040](../../adr/adr-0040.md)

4. **Repair at the provider boundary, in a fixed order.** Right before each model call, and again on each result, the list passes one repair pipeline: fill empty content, drop orphaned tool calls, merge same-role neighbours. The order is data, not a sequence of statements, so reordering it is a visible edit. → [ADR-0040](../../adr/adr-0040.md)

5. **Re-seed what compaction would lose.** The journal index is injected on a session's first turn and baked into every summary, so it survives compaction without any per-turn detection. → [ADR-0042](../../adr/adr-0042.md)

### Invariants

| Must stay true | If it breaks | Pinned by |
| --- | --- | --- |
| A tool call still awaiting its result survives compaction in native, resumable form | pydantic-ai cannot match the deferred result to a `ToolCallPart` that was flattened away | `test/llm/summarizer/history_processor/test_verbatim_tail.py::test_a_trailing_deferred_call_stays_in_native_message_form` |
| The real opening user message survives every compaction round | The model loses the task's goal; a later round keeps an old summary instead | `test/llm/summarizer/history_processor/test_history_summarizer_preservation.py::test_summarize_history_second_round_preserves_the_true_first_user_message` |
| A summarizer that cannot be built leaves the history unchanged | A missing API key for the small model kills every turn | `test/llm/summarizer/history_processor/test_summarizer_resilience.py::test_processor_survives_unbuildable_summarizer` |
| Repair keeps a tool call whose approved result is pending | The approved call is deleted and its result has nothing to answer | `test/llm/agent/run/test_history_utils_strip_to_text.py::test_sanitize_history_allow_orphaned_tool_calls_keeps_pending_call` |
| A failed write leaves the conversation marked unsaved | The cache evicts the only copy of the turn | `test/llm/history_manager/test_file_history_manager_parts.py::test_save_handles_os_error` |
| An unsaved in-memory update wins over a newer file on load | An external write between update and save discards the turn | **unpinned** |
| A context-length failure saves the history without growing it | Every retry is longer than the last and fails the same way | `test/llm/task/test_history.py::TestHandleRunError::test_skips_partial_summary_on_context_length` |

## Realization

### The parts

```mermaid
flowchart TD
    Task[LLMTask] -->|name and manager| Hist[LLMTaskHistory]
    Hist --> Files[FileHistoryManager]
    Task -->|history| Run[run_agent]
    Run -->|once per turn| Proc[summarizer processor]
    Proc --> Sum[summarize_history]
    Run -->|every round| San[sanitize_history]
```

| Part | Where | What it is responsible for |
| --- | --- | --- |
| `LLMTaskHistory` | `src/zrb/llm/task/history.py` | Picks the manager and the conversation name; saves what a failed or cancelled turn did |
| `resolve_conversation_name` | `src/zrb/llm/task/shared_getters.py` | The configured name, or a fresh random one when it is blank |
| `FileHistoryManager` | `src/zrb/llm/history_manager/file_history_manager.py` | The default store: a small LRU cache, load-time cleanup, validated atomic JSON writes, backups and retention |
| `AnyHistoryManager` | `src/zrb/llm/history_manager/any_history_manager.py` | The protocol a custom store implements: `load`, `update`, `save`, `search` |
| `create_summarizer_history_processor` | `src/zrb/llm/summarizer/history_summarizer.py` | Builds the processor that runs both tiers: first per-message, then the whole conversation |
| `process_message_for_summarization` | `src/zrb/llm/summarizer/message_processor.py` | Tier one: shrinks one oversized tool result, or truncates it if summarizing fails |
| `summarize_history` | `src/zrb/llm/summarizer/history_summarizer.py` | Tier two: splits the list, summarizes the old part, rebuilds the list |
| `split_history` | `src/zrb/llm/summarizer/history_splitter.py` | Finds a token-budget cut, preferring the start of a turn |
| `sanitize_history` | `src/zrb/llm/agent/run/history_utils.py` | The provider-boundary repair pipeline: a fixed tuple of steps, run in order |
| `PartialRunAccumulator` | `src/zrb/llm/agent/run/partial_run.py` | Records what a turn did as it streams, so a failed turn can be saved honestly |

### How it runs

**One turn.** `LLMTask` loads the history in a worker thread, hands it to `run_agent`, and saves what comes back:

```mermaid
sequenceDiagram
    participant T as LLMTask
    participant M as FileHistoryManager
    participant R as run_agent
    participant S as summarize_history
    T->>M: load(name)
    M-->>T: messages
    T->>R: run with messages
    R->>S: compact if over threshold
    S-->>R: compacted list
    R->>M: checkpoint after each tool round
    R-->>T: new history
    T->>M: update, then save
```

**Loading.** `load` serves the cache while the file's modification time is unchanged, or while the entry has unsaved updates. Otherwise it reads the file, cleans broken parts, and validates it. A missing, empty or invalid file gives an empty list with a warning, so a bad file never blocks a turn.

**Compacting.** The processor runs inside `run_agent`, between the `PreCompact` and `PostCompact` hooks, and counts the system prompt against the threshold. Tier one runs on every turn. Tier two runs only when the list is over the message window or the token threshold. When only the message count is over, it is skipped if summarizing would free too small a share of the token budget to be worth a model call. `summarize_history` then:

1. splits the list with `split_history` into an old part and a kept tail;
2. summarizes the old part in chunks, consolidating the snapshots if there are many;
3. adds the journal index to the summary text;
4. returns the restoration message, then the first real user message, then the kept tail rendered as text, then any still-unresolved tool call kept in native message form (orphaned tool results dropped from that native tail, same-role neighbours merged).

The cut in step 1 is chosen by budget, not by count: `LLM_HISTORY_TAIL_BUDGET_RATIO` of the trigger threshold, held under `LLM_HISTORY_TAIL_MAX_TOKENS`, landing on a turn boundary when one still keeps half of it, and retried at twice the ratio when the newest message alone overflows. A tail is measured as the text it is sent as (`count_tail_tokens` renders it with the same clip step 4 applies), not as the messages it came from and not with the provider's usage count on its newest response: that count covers the whole history before it, so read as the size of a suffix it reports the unsplit list, and the unclipped messages are up to four times what the request is actually charged for. The whole history is the exception that proves the rule — at split zero nothing is rendered, so `count_history_tokens` asks for its content size instead, or a tool-heavy history would "fit" a budget it overruns by an order of magnitude and be left whole by a compaction that summarized nothing. A counting subclass keeps its own counter, the same reason the bisected scan declines to trust one. → [ADR-0130](../../adr/adr-0130.md)

**Saving.** `save` serializes the list, validates it, writes a sibling `.tmp` file and renames it over the live one. The final save of a turn may also write a timestamped backup; mid-turn checkpoints pass `write_backup=False`.

### Variations

| Case | Where it is decided | What is different |
| --- | --- | --- |
| Mid-turn checkpoint | the stream handler in `src/zrb/llm/agent/run/runner.py` | Saved in the background whenever the list ends in a completed tool round; all checkpoints finish before the turn returns |
| The turn fails | `LLMTaskHistory.handle_run_error` | Closes dangling tool calls, appends an error note and a summary of the tools that ran |
| A context-length failure | `LLMTaskHistory.handle_run_error` | Saves the history as it was, with nothing appended |
| The user cancels | `LLMTaskHistory.save_cancelled_history` | Saves the live messages, closes dangling calls, adds an "interrupted" reply |
| `/compress` | `LLMTask`, before any agent is built | Runs `summarize_history` with `force=True`, even under the threshold |
| A `PreCompact` hook blocks | `run_agent` history preparation | Summarization is skipped; the emergency prune to the last message still runs if the list does not fit |
| A delegated sub-agent's transcript | `src/zrb/llm/util/subagent_session_naming.py` | Saved under `subagent/{agent}/` with no backup, and pruned by count — see [Sub-agents](../2-extension-surface/sub-agents.md) |
| An old auto-named conversation | `FileHistoryManager` on its first save | Deleted once it is older than `LLM_HISTORY_RETENTION`, whether it still has just its generated name or a `-topic` after it (see `LLM_AUTO_NAME_ENABLED`); a name someone chose is never pruned |

### Change it here

| To… | Open | Then run |
| --- | --- | --- |
| Change naming or what a failed turn saves | `src/zrb/llm/task/history.py` | `test/llm/task/test_history.py` |
| Change caching, file layout, backups or retention | `src/zrb/llm/history_manager/file_history_manager.py` | `test/llm/history_manager/` |
| Change when or how history is summarized | `src/zrb/llm/summarizer/history_summarizer.py` | `test/llm/summarizer/` |
| Change where the list may be cut | `src/zrb/llm/summarizer/history_splitter.py` | `test/llm/summarizer/history_processor/` |
| Change the provider-boundary repair | `src/zrb/llm/agent/run/history_utils.py` | `test/llm/agent/run/` |
| Change what a partial run records | `src/zrb/llm/agent/run/partial_run.py` | `test/llm/agent/run/test_partial_run.py` |

## See Also

- [The LLM Turn](../1-spine/llm-turn.md) — the loop this history feeds
- [LLM History Sanitization](../../technical-specs/llm-history-sanitization.md) — the provider quirks the repair pipeline handles
- [LLM Context](../../technical-specs/llm-context.md) — how the context window is budgeted
- [Sub-agents](../2-extension-surface/sub-agents.md) — where delegated transcripts go

🔖 [Documentation Home](../../README.md) > [Architecture](../README.md) > History & Compaction
