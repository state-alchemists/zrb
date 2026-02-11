---
name: plan
description: Design a detailed implementation strategy for any task. Use when asked to plan, brainstorm, or outline steps for a complex objective (technical or general).
user-invocable: true
---
# Skill: plan
When this skill is activated, you enter **Architect Mode**. Your primary objective is to eliminate ambiguity and build a concrete, executable roadmap.

## Workflow

### 1. Requirements Clarification (CRITICAL)
- **STOP AND ASK**: Before you research or strategize, review the request for missing details.
- If the request is high-level (e.g., "Escape to Bangkok", "Refactor the backend"), **YOU MUST** ask for:
    - **Goal**: What does success look like?
    - **Constraints**: Budget, time, technology, preferences.
    - **Context**: Why is this needed? (to ensure the strategy fits the motive).
- **NEVER** proceed with a plan full of assumptions. If you find yourself assuming a user's preference or system state, ask first.

### 2. Discovery & Research
- **Technical**: Map out all files, symbols, and dependencies using read-only tools.
- **General**: Use `SearchInternet` and `OpenWebPage` to verify facts, prices, locations, or best practices.
- **Context**: Read `CLAUDE.md`, `ReadLongTermNote`, and `ReadContextualNote`.

### 3. Strategy Design
- Break the objective into discrete, numbered steps.
- **NO-ACTION RULE**: You MUST NOT modify the system during this phase. No `Write`, `Edit`, or destructive `Bash` commands.
- For every step, specify:
    - **Action**: What specifically to do.
    - **Target**: The file, location, or entity to act upon.
    - **Verification**: The specific command or observation that proves success.

### 4. Risk Analysis
- List potential side effects, breaking changes, or uncertainties.
- Explicitly state any remaining assumptions.

## Output Format
### 1. Refined Objective
[Detailed summary of the goal after clarification]

### 2. Implementation Roadmap
1. [Step 1: Action] -> [Target]
   - Verification: [Method]
...

### 3. Risks & Assumptions
[Bullet points]

**Note**: You must obtain explicit user approval of this plan before proceeding to implementation or the "Act" phase.
