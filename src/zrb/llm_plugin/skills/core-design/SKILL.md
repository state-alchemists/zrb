---
name: core-design
description: "Activate before any design work — system architecture, API design, data modeling, component decomposition, or trade-off analysis. Provides the Constraints → Explore → Decide → Specify → Plan workflow for sound, well-reasoned designs."
user-invocable: false
---
# Skill: core-design

Follow **Constraints → Explore → Decide → Specify → Plan** for every design task.

## Companion Templates

When the current step matches a trigger below, `Read` the named companion from this skill's directory (path provided in the activation header). Companions are not pre-loaded — pull them on demand.

| Trigger | Companion |
|---------|-----------|
| Recording a design decision worth preserving (during or after the Decide step) | `templates/decision-record.md` |

## Workflow

### 1. Constraints & Requirements

- Extract explicit requirements and implicit constraints from the task.
- Identify what's in scope and what's out.
- Note non-negotiables: existing interfaces, backward compatibility, security, performance targets.
- If requirements are ambiguous, ask before designing further.

### 2. Architecture Exploration

- Generate 2-3 distinct approaches. Avoid converging on the first idea.
- Compare each approach against: correctness, consistency with existing patterns, complexity, performance, maintainability, testability.
- Use `Grep`, `Glob`, and `Read` to study existing patterns before proposing new ones.
- For large or unfamiliar domains, activate `core-research` first to map the landscape.

### 3. Design Decision

- Choose the best approach with explicit rationale.
- Document what was chosen AND what was rejected and why.
- The rationale should be specific enough that someone else could reconstruct the same decision from the constraints.

### 4. Specification

- Define precise contracts: interfaces, data flow, error modes, edge cases.
- Be concrete enough that implementation is straightforward from the spec alone.
- Use `WriteTodos` to capture loose ends or open questions.

### 5. Implementation Plan

- Break the design into discrete implementation steps.
- Each step: Action → Target → Verification.
- Order steps by dependency (what must exist before what).

## Safety Rules

- **No premature implementation**: During steps 1-4, do not write or modify any code. Design decisions come before implementation.
- **Approval gate**: You must obtain explicit user approval of the design and plan before starting implementation.

## Output Standards

- **Structured**: Clear sections matching the workflow above.
- **Precise**: Specific interfaces, types, and contracts — not vague descriptions.
- **Context-aware**: The design must fit the existing codebase, not introduce a new paradigm unless justified.
- **Transparent**: Surface trade-offs made and alternatives considered.