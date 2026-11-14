🔖 [Documentation Home](../README.md) > [Configuration](./) > [LLM Configuration](llm-config.md) > Context

# LLM Conversation Context

How long conversations are summarized, what the memory store keeps across sessions, and how `/rewind` snapshots your files.

## Table of Contents

- [Summarization Thresholds](#summarization-thresholds)
  - [What happens when a conversation gets long](#what-happens-when-a-conversation-gets-long)
  - [The knobs](#the-knobs)
  - [Why the tail is smaller than the ratio it was given](#why-the-tail-is-smaller-than-the-ratio-it-was-given)
  - [The archive](#the-archive)
  - [The summary itself](#the-summary-itself)
  - [Other oversized content](#other-oversized-content)
  - [Round cost, and the batch tool call nudge](#round-cost-and-the-batch-tool-call-nudge)
- [Memory & Notes Storage](#memory--notes-storage)
- [Rewind & Snapshots](#rewind--snapshots)
  - [Python API](#python-api)
  - [`/rewind` commands](#rewind-commands)

---

## Summarization Thresholds

Zrb summarizes in the background when history or a single message grows too large, so a long conversation keeps going instead of failing against the model's context window. Three things happen, in this order:

1. **A message too big is pruned on its own.** An oversized tool result keeps a token-budgeted head and tail; the middle is replaced by a marker and the path to a file holding the output verbatim. No model rewrites it, so the evidence cannot drift into a paraphrase before the compaction step sees it.
2. **A conversation over the threshold is compacted.** The older part is replaced by a briefing — where the work stands, what was in flight, what comes next, the decisions and the landmines — and whatever a resumed agent needs beyond prose is carried over beside it.
3. **What was replaced is archived.** Every replaced message is written word for word to a file, append-only, and the summary names that file, so detail dropped from context is still readable later.

A compacted history is therefore not just a summary. This is what the next turn loads:

```mermaid
flowchart TD
    Hist[History over the threshold] --> Cut[Split on the tail budget]
    Cut -->|older messages| Sum[Briefing summary]
    Cut -->|opening user message| Open[Kept word for word]
    Cut -->|recent messages| Tail[Kept as rendered text]
    Cut -->|pending tool call| Pend[Kept native and resumable]
    Sum -.->|also written in full| Arch[(Verbatim archive)]
    Sum --> Next[The list the next turn loads]
    Open --> Next
    Tail --> Next
    Pend --> Next
```

Two details of that picture are easy to miss. The recent tail is rendered back into the request as text rather than resent as separate structured messages, and each tool result inside it is cut to 2,000 characters with the omitted count stated in its place — the tail is a handover, not evidence. A tool call still waiting for its result is the exception, kept as a real call so it can be resumed rather than flattened away.

### The knobs

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD` | Token count triggering full history summarization. Left unset, it is recomputed on every request from the run's actual model (`/model` included): 75% of the model's known context window, or of `MAX_TOKEN_PER_REQUEST` for a model zrb doesn't recognize, and never more than `200000` however large that window is. Set explicitly — its own env var, or `DEFAULT_LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD` in `zrb_init.py` — it is a fixed value instead | The smaller of `200000` and 75% of the effective context window |
| `ZRB_LLM_MESSAGE_SUMMARIZATION_TOKEN_THRESHOLD` | Token budget for one tool result before it is pruned to a head, a tail and a pointer to the verbatim file | `8000` |
| `ZRB_LLM_HISTORY_SUMMARIZATION_WINDOW` | Most messages kept verbatim after summarization | `300` |
| `ZRB_LLM_HISTORY_TAIL_BUDGET_RATIO` | Share of the summarization threshold the verbatim tail may fill. The newest messages that fit it are kept word for word instead of summarized. It is a budget, not a target: the splitter usually keeps less. Values outside `0.05`–`0.8` are clamped | `0.4` |
| `ZRB_LLM_HISTORY_TAIL_MAX_TOKENS` | Absolute ceiling on the verbatim tail, in tokens, applied on top of the ratio: whichever is smaller wins, including on the retry that fires when the newest message alone overflows. `0` leaves the ratio in charge | `12000` |
| `ZRB_LLM_SUMMARY_MAX_TOKEN_RATIO` | Share of the summarization threshold one summary may fill; a summary over it is shortened before it replaces the history. `0` disables the cap | `0.05` |

A tool result over `ZRB_LLM_MESSAGE_SUMMARIZATION_TOKEN_THRESHOLD` keeps the first 75% and the last 12.5% of what the marker leaves, with `[... N tokens pruned ...]` where the middle was. The marker, the pointer and the separators are paid for out of the threshold, so the replacement never exceeds it; the effective budget is at least 64 tokens and at least the measured size of the marker and the pointer, so a path is never truncated to fit — a long `LLM_HISTORY_DIR` therefore raises the floor. The replacement's first line names the output's size and the absolute path of its verbatim copy, under `<LLM_HISTORY_DIR>/verbatim/<conversation>.tool-results/`. That directory is collected when no transcript names it any more — with or without a verbatim archive, since a result can be pruned long before its conversation ever compacts — so nothing pruned outlives the history that pointed at it, and a result that could not be saved says so instead of naming a path that does not exist. The budget is its own knob: it does not scale with the compaction trigger, so a result is pruned long before the conversation reaches the point of being summarized.

Compaction has two halves, and each is bounded differently. The summary is bounded by `ZRB_LLM_SUMMARY_MAX_TOKEN_RATIO`; the kept tail by `ZRB_LLM_HISTORY_TAIL_BUDGET_RATIO`, held under `ZRB_LLM_HISTORY_TAIL_MAX_TOKENS`, whichever of the two is smaller. The ratio on its own would allow 80,000 tokens of tail on the default 200,000-token trigger — nearly half of it, re-read on every later turn — which is what the ceiling is there to prevent: at its default 12,000 the ceiling is what binds, not the ratio. The summary's share on the same trigger is 10,000.

### Why the tail is smaller than the ratio it was given

The ratio is a budget, not a target, and the tail usually comes in under it, for three reasons worth knowing before you change the number:

- **It prefers a turn boundary.** The splitter walks back from the newest message to the earliest point that fits, and prefers a user message when that boundary still keeps at least half the budget. A budget of 0.3 and one of 0.4 can therefore produce the very same tail, because the boundary binds first.
- **The message window caps the count.** `ZRB_LLM_HISTORY_SUMMARIZATION_WINDOW` stops the tail at 300 messages regardless of tokens, which is what bounds a long session of small messages.
- **If nothing fits, the retry follows the ratio.** When even the newest message alone is bigger than the budget — one huge tool result, say — the splitter retries at twice the ratio, capped at 0.8. That retry is the only case where the tail can exceed your setting, and never by more than that factor. Only when neither budget fits is nothing kept.

Lowering the ratio makes compaction more lossy by design: the tail exists to carry recency, so a smaller tail means more of the recent conversation reaches the next request only as summary. Counting follows `ZRB_TIKTOKEN_ENABLED`; the default `char/4` estimate runs about a tenth low against a real tokenizer on code- and path-heavy text, so treat these numbers as a budget rather than a bill. The count the banner reports for the kept tail is the size of the text that tail is sent as — each tool result inside it already clipped to 2,000 characters — not the size of the unclipped messages and not the size of the history it was cut from, so a tail the banner calls 12,000 tokens weighs 12,000 in the next request, to within the few tokens of the turn that carries it.

### The archive

What a summary replaces is also written word for word, append-only, to `<history dir>/verbatim/<session>.md` — the history directory the conversation is actually stored in, `ZRB_LLM_HISTORY_DIR` unless a custom history manager says otherwise — and, if the archive write succeeds, the summary names that file so the agent can read back the detail it dropped. The two go together in both directions: when the cap has room for the summary but not for that paragraph, nothing is written, because a file no summary names is one the cleanup may delete while it is still the only copy. The archive holds the history as the conversation held it, before oversized tool results were reduced to summaries, so a tool's output remains available after compaction.

An archive is pruned, with its lock sidecar, only once **no history refers to it**: no transcript anywhere in the history tree — the conversation's own file, a backup of it, or a delegated sub-agent's transcript under `subagent/<agent-type>/` — carries its pointer, and it is older than `ZRB_LLM_HISTORY_RETENTION` (so an archive written just before its history is saved is never mistaken for an orphan, and `0` keeps every archive). Sub-agent transcripts are searched because they point at the same shared `verbatim/` directory. That keeps the directory bounded without leaving a summary pointing at text that is gone. Archives may still contain sensitive text: protect access to the history directory and back it up as needed.

A directory written before these permissions existed is narrowed **once**, on first use, with a marker (`<dir>.owner-only`) beside it so later runs leave it alone — a mode you change back after that stays as you set it. This applies to both the history directory and the memory store.

### The summary itself

The summary reaches the next model as a fenced block that names itself: it opens with `# SYSTEM: Automated Context Restoration`, says in as many words that it is derived data rather than the user speaking, and closes with an explicit end marker. Both are load bearing, because role alternation merges the summary into the same user turn as the real user messages that follow it, and without them the reader cannot tell the automation from the user. Its size is bounded by `ZRB_LLM_SUMMARY_MAX_TOKEN_RATIO`, a share of the trigger threshold rather than a fixed count, so the bound follows the model's window: 0.05 is 10,000 tokens on the 200,000-token default trigger, with a 1,000-token floor below that. The bound is measured on the block as it will be inserted — zrb's own framing, the snapshot, the memory block and the archive pointer. A block over it is shortened at most twice and then cut, losing whole sections from the least durable end first and keeping the closing tag; a summary that arrived without the schema is bounded on the same rule rather than dropped, since an over-budget history fails the request where a bulky summary only costs tokens. If the framing and notes fill the cap on their own, the snapshot is dropped and the warning names the setting to raise. A summary that comes back empty leaves the history untouched instead.

### Other oversized content

The same mechanism keeps one large repo or file read from blowing the context window; like the conversation thresholds above, each of these is clamped to a fraction of the smaller of `MAX_TOKEN_PER_MINUTE` and `MAX_TOKEN_PER_REQUEST` (75% for those two, 40% here):

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD` | Token count above which repo-analysis content is extracted in chunks | 40% of `MAX_TOKEN_PER_REQUEST` |
| `ZRB_LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD` | Token count triggering summarization of repo-analysis results | 40% of `MAX_TOKEN_PER_REQUEST` |
| `ZRB_LLM_FILE_ANALYSIS_TOKEN_THRESHOLD` | Token count above which a single file's analysis is summarized | 40% of `MAX_TOKEN_PER_REQUEST` |

### Round cost, and the batch tool call nudge

Every round re-sends the whole conversation, so a turn that issues sixty tool calls one at a time pays for its context sixty times: an agentic turn's input grows with rounds × history size, not with the output it produces. A response may carry several calls at once, and independent ones are cheaper together — that is the one lever that needs no threshold change.

The prompt asks the model to batch; when that is ignored, zrb injects one reminder, controlled by `ZRB_LLM_BATCH_TOOL_CALL_NUDGE_ENABLED` (on by default). Three consecutive rounds that each carried a single lookup call — `Read`, `Grep`, `Glob` or `LS`, in any mix — on *different* arguments is what it counts, and the reminder says why in one line — this is the whole text, so a transcript carrying it can be recognised:

```text
[SYSTEM SUGGESTION]: batching — the last 3 rounds each carried one `Read` call on different arguments. If those calls did not depend on each other's results, put them in one response: each extra round re-sends the whole conversation.
```

A streak that mixed the tools names none of them: the same sentence reads `…each carried a single lookup on different arguments.` The tool is part of what was asked, so `Grep x` after `Glob x` counts as two lookups, while the same tool on the same arguments is one lookup repeated and is not counted.

`Shell`, `Write` and `Edit` are never counted — there the next call usually depends on what the previous one printed, so batching them would be wrong — and the reminder is said at most once per user turn: a turn that keeps issuing one lookup per round after being told stays silent for the rest of that turn, and a turn that begins after it is told again. The turn is the boundary, so an hour later, a new topic, or a conversation resumed after a compaction hears the rule afresh. It reaches sub-agents too, since a delegated run pays the same price.

`/usage` reports the shape beside the totals: **tool calls per round**. A window of several rounds averaging one call per round was issuing lookups serially; the same calls issued two or three to a response would have cost a fraction of the input tokens.

The tokens have a shape too. On the round that opens a turn, `/usage` counts what the request was made of — the system prompt, the fitted history, and your own message — and prints that split beside the provider's own input for the same request. Both are shown because they answer different questions: the split says whether the history is the weight or the instructions are, and the gap between them says how much framing the provider adds over a local count. Tool definitions are not in the split, because their weight is a constant of the configuration rather than of the turn, and it moves with the number of visible tools rather than with their prose ([ADR-0058](../adr/adr-0058.md)).

The same arithmetic is what `/usage`'s one forward-looking line measures. A conversation left idle past the provider's prompt-cache lifetime re-sends its whole history on the next turn. On 2026-11-12 three turns began 37, 21 and 127 minutes after the previous one, at 67.0%, 49.9% and 49.8% cached, and paid 351,517 fresh input tokens to produce 5,484 output — a fifth of that day's fresh input — where a cold session pays 18–24k before the first word. When the history holds more than [`ZRB_LLM_UI_USAGE_RESUME_HISTORY_TOKENS`](llm-limits.md#usage-resume-line) and its newest message is older than `ZRB_LLM_UI_USAGE_RESUME_GAP_SECONDS`, `/usage` prints what each choice costs next.

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_LLM_BATCH_TOOL_CALL_NUDGE_ENABLED` | Remind the model, once per user turn, that three consecutive rounds each carried a single lookup call — `Read`, `Grep`, `Glob` or `LS`, in any mix — on different arguments. `off` leaves the conversation untouched: the reminder is never injected. It is withheld too for a model whose `supports_parallel_tool_calls` is `False` | `on` |

The reminder is withheld for a model on zrb's parallel-call deny-list (`supports_parallel_tool_calls` is `False`): the System Context already tells such a model to issue exactly one call per response, and a reminder arguing the other way would cost it both calls in the round. An unrecognised model is treated as able, since the list names only models known to malform.

## Memory & Notes Storage

How the store works — its files, what reaches the model and when — is explained once, in [LLM Memory](../technical-specs/llm-memory.md). This section lists the knobs.

The journal's fourteen `ZRB_LLM_JOURNAL_*` settings are retired. A start that still sets one names it and what to set instead, from the list in `src/zrb/config/retired.py`: the directory became `ZRB_LLM_NOTES_DIR`, the git backing and the judge became `ZRB_LLM_MEMORY_GIT_ENABLED` and `ZRB_LLM_MEMORY_REVIEWER_ENABLED`, the lock timeout became `ZRB_LLM_MEMORY_LOCK_TIMEOUT`, and the rest controlled a system that no longer exists.

> **Note on White-labeling:** the `ZRB_` prefix and the `~/.zrb/` paths below are the stock build's. A white-labeled build reads its own `<PREFIX>_LLM_…` variables and puts the notes directory under its root group name (`~/.<ROOT_GROUP_NAME>/llm-notes/`, e.g. `~/.acme/llm-notes/`). See [White-labeling](../advanced-topics/white-labeling.md).

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_LLM_MEMORY_ENABLED` | The privacy switch, not a choice between stores. `off` unregisters `SearchMemory`, `Remember` and `Forget`, suppresses the `<memory>` block and the reviewer, and leaves the store untouched on disk — the session neither reads nor writes a memory, and nothing takes its place | `on` |
| `ZRB_LLM_NOTES_DIR` | The notes directory: the store lives inside it as `memory-v1`, and it is what `zrb memory migrate` reads. One directory to back up, and the notes an older zrb wrote stay beside the store. `.version` at its root records that they were read | `~/.zrb/llm-notes/` |
| `ZRB_LLM_MEMORY_DIR` | The store itself: `core.md`, `facts/`, `diary/`, `week/`, `log/` and a git repository. Point it at an Obsidian vault subfolder to browse memory as a graph. The version segment keeps an older install from reading a newer format as its own | `<ZRB_LLM_NOTES_DIR>/memory-v1` |
| `ZRB_LLM_MEMORY_CORE_MAX_CHARS` | Characters of `core.md` — the pinned claims and open loops injected on a conversation's first turn. The cap is enforced by refusal, not truncation: a pin that does not fit fails and names the deficit. `0` means no pins fit and the core is never written | `4000` |
| `ZRB_LLM_MEMORY_RECENT_MAX_CHARS` | Characters of the `## Recent` block injected beside the core: the week note, the newest handover, today's diary claim, the last day written and the last few log lines — in that order, which is also the eviction order, so the log tail is what the cap cuts first. Whole lines only | `1600` |
| `ZRB_LLM_MEMORY_RECENT_LOG_LINES` | Log lines `## Recent` carries, today's first and yesterday's when today is short. `0` drops them and keeps the handover | `4` |
| `ZRB_LLM_MEMORY_REVIEWER_ENABLED` | The background reviewer that reads each completed turn and writes what is durable. Its normal answer is "nothing", so it costs one small-model call on a turn that recorded nothing. `off` leaves writing to the agent's own `Remember` calls | `on` |
| `ZRB_LLM_MEMORY_GIT_ENABLED` | Commit every memory write, so git is the audit log and the undo button. A commit that fails never fails the write | `on` |
| `ZRB_LLM_MEMORY_LOG_RETENTION_DAYS` | Days of `log/` kept. `0` keeps every log day; a positive value deletes a day's log once it is older than that, which is the one destructive operation memory has. Facts and diary entries are never pruned | `0` |
| `ZRB_LLM_MEMORY_LOCK_TIMEOUT` | Seconds a memory write waits for another writer before failing. The lock is taken before the file is read, so two writers on one subject cannot drop each other's revision | `30` |
| `ZRB_LLM_SELF_REVIEW_ENABLED` | Built-in self-review Stop hook. On a turn that changed files, a fresh-context reviewer reads the working directory's diff since the turn started (every repository under it, nested ones and worktrees included; shell edits and mid-turn commits included; earlier uncommitted work excluded) plus read-only surrounding code. A `Request changes` verdict extends the turn so the agent fixes the findings. Snapshots go to a private temporary git store, never your `.git/objects`. Costs two snapshots per turn (start and Stop) and one reviewer run per turn that changed files | `off` |
| `ZRB_LLM_SELF_REVIEW_MAX_ROUNDS` | Consecutive blocking reviews in one turn before it ends anyway; a non-blocking review resets the count | `2` |
| `ZRB_LLM_SELF_REVIEW_MODEL` | Reviewer model. Empty uses the run's model; a different model shares fewer blind spots | (empty) |
| `ZRB_LLM_SELF_REVIEW_TIMEOUT` | Seconds per review. On timeout the reviewer (and its model request) is cancelled and the turn ends unreviewed | `240` |
| `ZRB_LLM_SELF_REVIEW_MAX_TRACKED_TURNS` | Turns whose blocking-review count is kept at once; a turn that ends mid-continuation never clears its own, so the oldest past this are dropped | `64` |
| `ZRB_LLM_HISTORY_DIR` | Conversation history directory | `~/.zrb/llm-history/` |
| `ZRB_LLM_HISTORY_RETENTION` | How long a conversation with a generated name (like `bold-arch-1234`, or `bold-arch-1234-greetings` once auto-named) is kept after its last save, backups included (`30d`, `2w`, …; `0` = keep all). A conversation you named — with `/save` or your own session name — is never pruned, unless the name you typed itself starts with a generated name such as `bold-arch-1234-`, which retention reads as an auto-named one. Pruned on the first save of each session | `30d` |
| `ZRB_LLM_AUTO_NAME_ENABLED` | Rename a conversation that still has its generated name, after its first message, to `<generated-name>-<topic>` (e.g. `bold-arch-1234-greetings`) using the small model. A name you chose is never renamed. Sub-agent transcripts and live sessions keep the generated name as their key, and each new sub-agent gets a topic title in the picker | `on` |
| `ZRB_LLM_AUTO_NAME_MODEL` | Model that names a conversation. Empty uses the small model (`ZRB_LLM_SMALL_MODEL`, else the main model) | empty |
| `ZRB_LLM_HISTORY_BACKUP_RETAIN` | Number of timestamped history backups to keep per conversation (`-1` = keep all, `0` = disable) | `3` |
| `ZRB_LLM_ARCHIVE_LOCK_TIMEOUT` | Seconds a verbatim archive append waits for another writer, so a rollback truncates only its own bytes. On timeout nothing is written and the summary carries no pointer (`0` = fail at once) | `30` |
| `ZRB_LLM_AGENT_MESSAGE_LIMIT` | Max messages the main agent and one delegated sub-agent may send each other (both directions together) before `SendMessageToSubagent` / `SendMessageToParent` refuse, so two agents cannot answer each other forever. Human messages do not count | `20` |
| `ZRB_LLM_SUBAGENT_HISTORY_RETAIN` | Max sub-agent transcripts kept across all agent types (`-1` = keep all); oldest pruned on each new delegation. Transcripts live under `ZRB_LLM_HISTORY_DIR/subagent/<agent-type>/` | `50` |
| `ZRB_LLM_USAGE_DIR` | Directory of the local usage log behind `/usage`: `usage-YYYY-MM.jsonl`, one line per completed run and one per compaction (token, request and tool-call counts, duration, and cost where the model is priced). Numbers and tool names only: no prompt text, tool arguments, file paths or file content | `~/.zrb/llm-usage/` |
| `ZRB_LLM_PREVIOUS_MESSAGE_HISTORY_DIR` | Directory of the cross-session history of submitted messages that `↑`/`↓` recall in the chat input box | `~/.zrb/llm-previous-message-history/` |
| `ZRB_LLM_PREVIOUS_MESSAGE_HISTORY_MAX_ENTRIES` | Most messages that history keeps; oldest dropped first (`0` = keep all) | `1000` |

## Rewind & Snapshots

Before each AI turn, Zrb snapshots your working directory so `/rewind` can restore any earlier state mid-session.

**How it works:** each snapshot is a commit in a private git store under `ZRB_LLM_SNAPSHOT_DIR` whose work tree is your directory, so nothing is copied and your own repositories' history, index and objects are never touched. Every repository under the directory is snapshotted by its own `.gitignore` (nested clones and submodules included); files outside any repository are taken as they are, minus common cache directories (`node_modules/`, `.venv/`, `__pycache__/`, …). Each conversation keeps its own rewind history: `/load` switches to the loaded conversation's history, and `/save` copies the current one to the new name.

**Limits and guarantees:**

- Files a repository's `.gitignore` excludes (even ones excluded only after a snapshot) are neither snapshotted nor restored — an edit to a gitignored `.env` is not rewound. A `.gitignore` outside any repository has no effect, as in git.
- Outside every repository, a directory may hold at most 5,000 files or 200 MB (`ZRB_LLM_SNAPSHOT_LOOSE_MAX_FILES`, `ZRB_LLM_SNAPSHOT_LOOSE_MAX_MB`). Past that (e.g. a chat started in `~`), or when `ZRB_LLM_SNAPSHOT_DIR` is the working directory itself, rewind turns off for the session and says why at startup and on `/rewind`.
- Rewind restores files, nested repositories' included, but never moves a repository's `HEAD` or branches, and leaves a repository created since the snapshot (a worktree or clone) alone.
- It removes a file only if the snapshot would have held it (never one that was ignored or unreadable then), and never overwrites a file it cannot read now.
- If a file cannot be written (held open, or read-only folder), the rest are still restored, `/rewind` names what was left behind, and re-running the same `/rewind` finishes the job.
- A file larger than 50 MB (`ZRB_LLM_SNAPSHOT_FILE_MAX_MB`) is left out, as if ignored: rewind neither restores nor removes it.
- Without git on `PATH`, rewind is off; startup says nothing, `/rewind` says why.
- A conversation's rewind history is dropped once its newest snapshot is older than `ZRB_LLM_SNAPSHOT_RETENTION` (never the current conversation's), and `git gc --auto` then packs the repository and prunes what no history holds.

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_LLM_REWIND_ENABLED` | Enable filesystem snapshots and `/rewind` command | `on` |
| `ZRB_LLM_SNAPSHOT_DIR` | Directory holding one snapshot git repository per working directory. Must not be the working directory itself | `~/.zrb/llm-snapshots/` |
| `ZRB_LLM_SNAPSHOT_FILE_MAX_MB` | A file larger than this is left out of every snapshot (rewind's and self-review's), as if ignored | `50` |
| `ZRB_LLM_SNAPSHOT_LOOSE_MAX_FILES` | Most files taken from outside every git repository; past it, rewind is off for the session | `5000` |
| `ZRB_LLM_SNAPSHOT_LOOSE_MAX_MB` | Most MB taken from outside every git repository; past it, the same | `200` |
| `ZRB_LLM_SNAPSHOT_COMMAND_TIMEOUT` | Seconds one snapshot git command may take before it is killed | `30` |
| `ZRB_LLM_SNAPSHOT_OPERATION_TIMEOUT` | Seconds one rewind snapshot or restore may take as a whole, once it holds the store; running out turns rewind off for the session | `120` |
| `ZRB_LLM_SNAPSHOT_LOCK_TIMEOUT` | Seconds a rewind operation waits for another session's operation on the same directory before that one operation fails | `60` |
| `ZRB_LLM_SNAPSHOT_RETENTION` | How long a conversation's rewind history is kept after its newest snapshot (`30d`, `2w`, …; `0` = keep all). Checked when a session starts in the same directory | `30d` |

### Python API

```python
from zrb import LLMChatTask

task = LLMChatTask(
    name="chat",
    enable_rewind=True,           # None → falls back to ZRB_LLM_REWIND_ENABLED
    snapshot_dir="/tmp/my-snaps", # None → falls back to ZRB_LLM_SNAPSHOT_DIR
)
```

### `/rewind` commands

| Input | Effect |
|-------|--------|
| `/rewind` | List the current conversation's snapshots (newest first) with index, short SHA, timestamp, and user message |
| `/rewind <n>` | Restore snapshot number `n` from the list (1-based) |
| `/rewind <sha>` | Restore by full or partial SHA |

Restoring rewinds **both** files and conversation history, so the AI's context matches the restored files.
