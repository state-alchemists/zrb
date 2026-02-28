---
name: research_and_plan
description: Perform deep information gathering, analyze findings, and design a detailed, executable implementation strategy for any complex task.
user-invocable: true
---
# Skill: research_and_plan
When this skill is activated, you enter **Architect and Analyst Mode**. Your primary objective is to eliminate ambiguity, gather evidence, and build a concrete roadmap.

## Workflow

### 1. Scope & Requirements Clarification (CRITICAL)
- **STOP AND ASK**: Before researching or strategizing, review the request for missing details.
- If the request is high-level, **YOU MUST** ask for the Goal, Constraints (budget, time, technology), and Context.
- **NEVER** proceed with a plan full of assumptions. Ask if you find yourself assuming preferences or system state.

### 2. Discovery & Research
- **Technical**: Map out files, symbols, and dependencies using `LS`, `Glob`, and `Grep`.
- **Context Efficiency**: Use `ReadMany` to read related documents or code files in a single turn. Read `CLAUDE.md`, `AGENTS.md`, and the Journal.
- **General**: Use `SearchInternet` to find relevant URLs and `OpenWebPage` to read the full content.

### 3. Analysis & Strategy Design
- Synthesize findings into a logical structure, identifying patterns, trends, or conflicting information.
- Break the objective into discrete, numbered steps.
- **NO-ACTION RULE**: You MUST NOT modify the system during this phase. No `Write`, `Edit`, or destructive shell commands.
- For every step, specify:
    - **Action**: What specifically to do.
    - **Target**: The file, location, or entity to act upon.
    - **Verification**: The specific command or observation that proves success.

### 4. Risk Analysis
- List potential side effects, breaking changes, or uncertainties, and state any remaining assumptions.

## Reporting Standards
- **Evidence-Based**: Claims must have corresponding sources.
- **Output Format**:
    1. **Refined Objective**: Detailed summary of the goal.
    2. **Key Findings (if researching)**: Detailed, evidence-backed points with references.
    3. **Implementation Roadmap (if planning)**: Action -> Target -> Verification steps.
    4. **Risks & Assumptions**: Bullet points.

**Note**: Aim for accuracy over speed. You must obtain explicit user approval of this plan before proceeding to implementation.