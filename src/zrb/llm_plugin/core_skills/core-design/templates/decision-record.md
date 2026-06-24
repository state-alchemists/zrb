# Architecture Decision Record (ADR) Template

Use this when core-design's **Decide** step produces a choice worth recording — anything a future reader (including the LLM in a later session) would want to reconstruct.

## File Location

Store ADRs under the project's documentation:

- Preferred: `docs/adr/NNNN-<short-slug>.md` (sequential, `0001`, `0002`, …)
- Acceptable: `.adr/`, `docs/decisions/`, or wherever the project already keeps them

Check first with `Glob` — match existing project convention rather than inventing one.

## Format

````markdown
# ADR NNNN — <short title in imperative or noun phrase>

- **Status**: Proposed | Accepted | Superseded by ADR NNNN | Deprecated
- **Date**: YYYY-MM-DD
- **Deciders**: <names or roles>
- **Context tags**: <comma-separated, e.g. auth, performance, storage>

## Context

What problem are we solving? What constraints apply? What changed that forces this decision now?

State the situation neutrally — anyone reading this in a year should understand *why this came up* without needing the surrounding conversation.

## Decision

The single sentence stating what was chosen, in active voice.

> We will use <X> for <Y>.

Then, if needed, 1–3 paragraphs of clarification. No more.

## Rationale

Why this option won. Tie back to the constraints in Context. Cite evidence (`file:line`, benchmarks, prior incidents).

## Alternatives Considered

Each alternative gets a short paragraph:
- **<Option A>** — why rejected.
- **<Option B>** — why rejected.

Be specific about what would have made the alternative win. ("We'd have chosen B if our throughput requirement were 10× higher.")

## Consequences

What this decision *commits us to* and what it *closes off*.

- **Positive**: <e.g., simpler operational model, fewer moving parts>
- **Negative**: <e.g., cannot horizontally scale beyond N without revisiting>
- **Follow-ups**: <concrete next steps — tests to write, docs to update, deprecations>

## Backlinks

- [ADR index](index.md)
- <other ADRs that depend on or relate to this one>
````

## Tone

- Past or present tense, never future ("will" is fine in the Decision line, not in the body).
- Specific over vague. "We chose Postgres 16 over Redis Streams because our queue depth is bounded by row count, not message rate" beats "Postgres seemed more appropriate."
- Don't apologize, don't editorialize. State the decision and the evidence.

## ADR Lifecycle

- **Proposed**: drafted but not yet agreed. Use during core-design's Decide step before user approval.
- **Accepted**: agreed and in force. Default after user approval.
- **Superseded**: replaced by a newer ADR. Add `Superseded by ADR NNNN` to the Status line; keep the file (do not delete history).
- **Deprecated**: the situation that motivated the decision no longer exists. Status line records why.
