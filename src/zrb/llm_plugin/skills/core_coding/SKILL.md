---
name: core_coding
description: Tactical workflow for safe, maintainable, and high-quality codebase creation/modification. Enforces top-notch engineering standards for all coding-related tasks.
user-invocable: false
---
# Skill: core_coding

When working on any coding or development task, you MUST follow this `Research -> Strategy -> Execution` workflow to ensure safety, maintainability, and seamless integration.

## PHASE 1: RESEARCH & DISCOVERY

a.  **High-Level Reconnaissance:**
    - Use directory listing tools (`LS`) with limited depth for initial structure mapping.
    - Identify: source directories, test directories, configuration files, entry points, and utility/helper modules.
    - NEVER use listing tools if you already know specific file paths or if a targeted glob search is possible.
b.  **Documentation & Context Analysis:** 
    - Read `README.md`, `AGENTS.md`, `GEMINI.md`, `CLAUDE.md`, dependency files (e.g., `pyproject.toml`, `package.json`), and configuration files.
    - Treat documentation as first-class code. Analyze `.md`, `.rst`, or `.txt` files to understand project architecture, design patterns, configuration options, usage examples, and constraints.
c.  **Targeted Architecture Discovery:**
    - Combine turns: Use `Glob` and `Grep` in parallel to map file structures, existing patterns, and available utility functions. 
    - Use `Grep` with specific `regex` and `file_pattern` to minimize noise.
    - **Context Efficiency**: If you need to read multiple related files, ALWAYS prefer `ReadMany` over multiple sequential `Read` calls.
d.  **Tool Efficiency Heuristics:**
    - **`Read` / `ReadMany`**: Use `Read` for single files. Use `ReadMany` to gather context from related files simultaneously. For large files, read specific line ranges.
    - **`Glob`**: ALWAYS prefer over `LS` for targeted discovery.
    - **`Grep`**: ALWAYS limit scope via `file_pattern` and specific `regex`.
    - **`Write` / `Edit`**: ALWAYS prefer surgical editing (`Edit`) over rewriting entire files.

## PHASE 2: STRATEGY & ARCHITECTURE

e.  **Formulate a Grounded Plan:**
    - Inside your mandated `<thinking>` block, formulate a strategy that prioritizes **Maintainability**, **Readability**, and **Testability**.
    - **Pattern Matching**: Your strategy MUST match existing project guidelines and patterns exactly (inferred from the code). The new code should be well integrated into the existing system, looking as though it were written by the original author.
    - **Reuse Over Reinvention**: Identify if existing helper or utility functions can be leveraged. If it makes sense to use them, do so instead of creating new ones.
    - **Design Principles**: Apply SOLID and DRY principles as much as possible.
    - Do not introduce new architectural patterns without explicit approval.
    - Define your testing strategy (how you will empirically verify the code change).
    - Plan updates to the documentation if the codebase change affects APIs, configurations, or behaviors.

## PHASE 3: EXECUTION (Plan -> Act -> Validate)

f.  **Act (Surgical Implementation):**
    - Make minimal, precise edits strictly related to the sub-task.
    - Write code that is easy to trace and easy to test.
    - Consolidate logic into clean abstractions rather than threading state across unrelated layers.
    - Prefer to only use existing libraries and established patterns. NEVER introduce new technical debt.
    - **Transition Safety (Strangler Pattern)**: The codebase must remain in a stable, runnable state throughout all phases of modification. When replacing or significantly refactoring an existing component (e.g., a file, function, or module), use a progressive approach:
        1. Create the new component alongside the old
        2. Update and verify all references to point to the new component
        3. Only then remove the old component.
        NEVER delete a functioning component before its replacement is fully integrated and validated.
    - **Code Smell Reporting**: If you encounter existing code smells or poorly structured code during your work, report it to the user.
    - **Update Documentation**: Keep documentation files in sync with code changes. Update configuration options, behavior, and verify that examples match the new implementation. Remove references to deprecated/removed functionality.

g.  **Validate (Zero-Regression & Verification):**
    - **Validation is the only path to finality.** You must always make sure nothing breaks with your fix/update.
    - For bug fixes: Empirically reproduce the failure BEFORE applying the fix.
    - After changes: Run relevant tests, linters, and type-checkers to confirm success. A code change is incomplete without automated verification.
    - **Test Maintenance**: If a test fails (whether a new one or an existing one affected by your change), you MUST fix it.
    - If validation fails, diagnose the failure in a `<thinking>` block and adjust your strategy. Do not blindly repeat actions.
h.  **Synthesis:** Update your journal with learned insights before your final response.