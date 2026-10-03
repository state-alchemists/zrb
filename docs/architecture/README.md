🔖 [Documentation Home](../../README.md) > Architecture

# Architecture

This section is the design of zrb. It explains what problem each part solves and which principles shape it, then shows where those principles live in the code. It's written for a **new maintainer**: someone who wants to understand zrb well enough to change it.

The design is the source. The [ADRs](../adr/README.md) record each decision in detail, and the code carries the decisions out. These pages connect the two.

## Table of Contents

- [Where to start](#where-to-start)
- [How each page reads](#how-each-page-reads)
- [The four tiers](#the-four-tiers)
- [Reading paths](#reading-paths)
- [Editing these pages](#editing-these-pages)
- [Where the rest lives](#where-the-rest-lives)

## Where to start

Read [The System](system.md) first. It's one page with one map and the rules that hold everywhere. Then read [Task Execution](task-execution.md) and [The LLM Turn](llm-turn.md). That's about thirty minutes, and everything else in this section builds on it.

## How each page reads

Every page has the same two halves, so you can stop after the first.

**Design: why it is shaped this way.** This half changes rarely.

- *The problem*: the forces that make this part hard.
- *Principles*: the three to five decisions that answer those forces, each linked to the ADR that records it.
- *Invariants*: what must stay true, what breaks if it doesn't, and the test that guards it.

**Realization: where it is in the code.** This half changes often.

- *The parts*: a map, then a table of the classes and functions involved.
- *How it runs*: the common path, with a diagram or two.
- *Variations*: the cases that take a different route.
- *Change it here*: what you want to do, which file to open, and which test to run.

Read Design to understand a part. Read Realization when you're about to change it.

## The four tiers

The pages go from general to specific. Each tier is useful on its own.

| Tier | The question it answers | Pages |
| --- | --- | --- |
| **0 · System** | What are the parts, and what must never break? | [The System](system.md) |
| **1 · Spine** | How does work flow, end to end? | [Task Execution](task-execution.md), [The LLM Turn](llm-turn.md) |
| **2 · Extension surface** | How do I add or change behaviour? | [Tools](tools.md), [UI](ui.md), [Prompts](prompts.md), [Hooks](hooks.md), [Config](config.md), [Sub-agents](sub-agents.md) |
| **3 · Peripheral flow** | How does this one feature work? | [Web Requests](web-requests.md), [Tool Call & Approval](tool-call-approval.md), [Sandbox Enforcement](sandbox-enforcement.md), [History & Compaction](history-and-compaction.md), [MCP & LSP Servers](mcp-and-lsp.md), [Dictation & Barge-in](dictation-barge-in.md) |

Tier 2 holds the parts that change most often. If you have one hour, spend it there.

## Reading paths

| If you are… | Read |
| --- | --- |
| New, with half an hour | [The System](system.md) → [Task Execution](task-execution.md) → [The LLM Turn](llm-turn.md) |
| Chasing a bug | [Change Map](change-map.md), which goes from a symptom to the file that causes it |
| About to own an area | that area's page: Design first, then the code its Realization names |
| Reviewing a design change | the page's Principles, then the ADRs they link |
| Writing a task or a tool, not changing zrb | the user guides instead: start at [Documentation Home](../../README.md) |

## Editing these pages

The two halves follow different rules.

- **Design** uses words that would survive a refactor. It names no private symbols. Every principle links its ADR, and every invariant names its test or is marked **unpinned**.
- **Realization** names real symbols, so it changes along with the code. Every backticked path and identifier is checked against `src/` and `test/`. If you rename something a page mentions, the build fails until you update the page.

When a principle changes, update its ADR first, then the page.

`test/architecture/test_architecture_docs.py` enforces the shape, the diagram limits (at most 120 columns, at most four participants, real class or function names only) and the truth check. Its docstring explains why each rule exists.

## Where the rest lives

| Question | Look at |
| --- | --- |
| Why was this specific decision made? | `docs/adr/`, in the record that owns it |
| What is the philosophy behind the whole shape? | [Architecture, Philosophy & Conventions](../contributing/architecture.md) |
| What rules must my code follow? | [Framework Conventions](../contributing/framework-conventions.md) (R1–R12) |
| What are the exact tables and edge cases? | `docs/technical-specs/` |
| Where does the code live? | `AGENTS.md`, under "Where the code lives" |
| How do I use this feature? | the guides in `docs/llm/`, `docs/core-concepts/` and `docs/task-types/` |

🔖 [Documentation Home](../../README.md) > Architecture
