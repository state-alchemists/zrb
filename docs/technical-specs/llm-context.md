🔖 [Documentation Home](../../README.md) > [Technical Specs](./llm-context.md)

# LLM Journal System (Technical Specification)

Zrb provides a directory-based journal system for maintaining persistent context across LLM sessions. This allows the assistant to remember project-specific details, user preferences, and local environment information through a hierarchical file system structure.

---

## Table of Contents

- [Overview](#1-overview)
- [Storage Mechanism](#2-storage-mechanism)
- [Prompt Injection](#3-prompt-injection)
- [Automatic Creation](#4-automatic-creation)
- [Configuration Placeholders](#5-configuration-placeholders)
- [Documentation Separation](#6-documentation-separation)

---

## 1. Overview

The journal is a directory of Markdown files organized hierarchically by topic or project, giving the assistant a structured place to keep context that outlives a single session.

| Property | Value |
|----------|-------|
| Storage | Directory of Markdown files |
| Organization | Four note categories plus a dated activity log |
| Entry point | `index.md`, the only file injected into a session |
| Written by | `LogActivity`, `WriteJournalNote` and `DeleteJournalNote`, which own the on-disk format |

---

## 2. Storage Mechanism

Journal entries are stored in a directory structure with a central index file.

Every journal knob (directory, index file, injection cap, HUD cap, first-turn auto-search, git backing) is listed in [LLM Configuration → Journal & Context Storage](../configuration/llm-config.md#5-journal--context-storage); the directory defaults to `~/.zrb/llm-notes/` and the index file to `index.md`.

`ZRB_LLM_JOURNAL_ENABLED=false` turns the whole subsystem off. There is no journal prompt section to suppress — the journal *is* its four tools (`SearchJournal`, `LogActivity`, `WriteJournalNote`, `DeleteJournalNote`), so the flag drops them from the per-run tool factories in `common_tools.py`, and `render_journal_index` checks the same flag for the `<journal-index>` injection. The model is then never told a journal exists (ADR-0055).

`ZRB_LLM_JOURNAL_DIR` is **not** an off switch: clearing it falls back to `~/.zrb/llm-notes/` rather than disabling journaling.

### Directory Organization

The writers create a fixed layout (`ensure_journal_tree` in `src/zrb/llm/tool/journal_write.py`): four note categories and an activity log, each with its own `index.md`.

```mermaid
flowchart LR
    Root["~/.zrb/llm-notes/"] --> Index["index.md — root index, auto-injected"]
    Root --> U["user/ — notes + index.md"]
    Root --> P["preferences/ — notes + index.md"]
    Root --> PR["projects/ — notes + index.md"]
    Root --> T["technical/ — notes + index.md"]
    Root --> A["activity-log/ — YYYY/YYYY-MM/YYYY-MM-DD.md"]
```

`WriteJournalNote` writes `<category>/<slug>.md`; `LogActivity` appends to the day file under `activity-log/`. With `ZRB_LLM_JOURNAL_GIT_ENABLED` on (the default) and `git` installed, the journal root is also a git repository and each write or delete is a commit.

### Index File Structure

The root index is created with this skeleton; `WriteJournalNote` adds a one-line summary of each note under `User`, `Preferences` or `Active Constraints` (for `projects` and `technical` notes):

```markdown
# Journal

## User

## Preferences

## Active Constraints

## Directories

- [user](user/index.md) · [preferences](preferences/index.md) · [projects](projects/index.md) · [technical](technical/index.md) · [activity-log](activity-log/index.md)

## Recent Insights
```

---

## 3. Prompt Injection

The `index.md` snapshot is deliberately kept **out of** the cached system prompt (`src/zrb/llm/prompt/live_context.py::render_journal_index`). Embedding the mutable index in the cached prefix would invalidate that cache every time the agent journaled mid-session (ADR-0042), so instead it travels through the conversation itself, as part of the `<live-context>` block appended to the latest **user** message — never the system prompt.

The index is only injected at the two moments it could otherwise be missing from context:

- **The first turn** — when history is still empty, `render_live_context(..., inject_journal_index=True)` appends the snapshot.
- **History summarization** — `summarize_history` re-seeds the index into the freshly-compressed history so it survives compaction.

On every other turn, the block is simply omitted — the agent is expected to already have it from earlier in the conversation.

When present, the block is wrapped as its own tag inside the live-context payload:

```
<journal-index>
Your persistent memory (index file: /abs/path/to/index.md). Use SearchJournal for full entries; a category's index.md (e.g. technical/index.md) lists every note ever written in it, uncapped. Change the journal only through LogActivity, WriteJournalNote, or DeleteJournalNote — ...
[content of index.md, capped at ZRB_LLM_JOURNAL_INDEX_MAX_CHARS]
[on the first turn, notes possibly related to the opening message, when ZRB_LLM_JOURNAL_AUTO_SEARCH_ENABLED is on]
</journal-index>
```

The header carries the **absolute path** of the index file, so the agent can `Read` the file directly when it needs more than the cap allows. The `SearchJournal` directive stays — searching is the intended interface for content, not dumping the whole file into context.

When the content exceeds the cap it is cut **on a line boundary** and ` (...more)` is appended, and the block marks the truncation:

```
Your persistent memory (index file: /abs/path/to/index.md). Truncated at `(...more)`. Use SearchJournal for full entries; ...
```

Cutting on a line boundary matters because the entries are facts about the user — half a sentence is worse than none. Overflow is dropped from the **end**, so the index should be written most-durable-first. `WriteJournalNote` enforces that order when it creates the root index: identity and standing preferences first, unbounded "Recent Insights" last, so growth only ever evicts itself.

Nothing is injected at all when the index file is missing, unreadable, or empty; when `ZRB_LLM_JOURNAL_INDEX_MAX_CHARS` is `0`; or when `ZRB_LLM_JOURNAL_ENABLED` is `false`. A missing block therefore does not prove an empty journal — and nothing tells the model so. Stating the caveat would cost either prompt weight or a tool docstring paid for on every request, so it is a known gap rather than shipped text (`render_journal_index`'s docstring records it). It matters only when `ZRB_LLM_JOURNAL_INDEX_MAX_CHARS` is `0` while the journal tools stay registered — a deliberate and unusual pairing.

---

## 4. Automatic Creation

`search_journal` (`src/zrb/llm/tool/journal.py`, exposed to the agent as `SearchJournal`) calls `os.makedirs(..., exist_ok=True)` when the configured directory is absent and reports the same empty result an unmatched search returns.

That behaviour is deliberate. Reporting a missing directory as an error made the whole memory layer read as unavailable, and the agent responded by declaring it could not journal rather than by writing its first note. An unwritten journal is *empty*, not broken.

**The rest of the tree is created by the writers, not by the agent.** `LogActivity` and `WriteJournalNote` (`src/zrb/llm/tool/journal_write.py`) derive every path and timestamp themselves, create the root index and the five directory indexes (four categories plus `activity-log`) on first write, and maintain the link graph — each note registered in its directory index, each forward link matched by a reciprocal backlink. The agent supplies content; the structure is code (ADR-0055).

---

## 5. Configuration Placeholders

The journal system uses configuration placeholders that are automatically replaced in prompts:

| Placeholder | Replaced With |
|-------------|---------------|
| `{CFG_LLM_JOURNAL_DIR}` | Journal directory path |
| `{CFG_LLM_JOURNAL_INDEX_FILE}` | Index filename |
| `{CFG_ROOT_GROUP_NAME}` | Root group name (e.g., "zrb") |
| `{CFG_LLM_ASSISTANT_NAME}` | Assistant name |
| `{CFG_ENV_PREFIX}` | Environment variable prefix |

---

## 6. Documentation Separation

| Location | Content Type |
|----------|-------------|
| `AGENTS.md` | Technical documentation (architecture, conventions, patterns) |
| Journal | Non-technical notes, reflections, project context |

> 💡 **Best Practice:** Use `AGENTS.md` for rules the LLM must follow. Use the journal for information the LLM should remember.

🔖 [Documentation Home](../../README.md) > [Technical Specs](./llm-context.md)
