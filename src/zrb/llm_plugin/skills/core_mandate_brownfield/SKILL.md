---
name: core_mandate_brownfield
description: Core mandate for discovering, understanding, and modifying existing codebases safely and efficiently.
user-invocable: false
---
# Skill: core_mandate_brownfield
When working in an existing repository, you MUST follow this `Research -> Strategy -> Execution` protocol to ensure safe, efficient, and successful modifications.

## PHASE 1: RESEARCH & DISCOVERY (Before Any Modification)

a.  **High-Level Reconnaissance:**
    - Use directory listing tools (`LS`) with limited depth for initial structure mapping.
    - Identify: source directories, test directories, configuration files, entry points.
    - NEVER use listing tools if you already know specific file paths or if a targeted glob search is possible.

b.  **Documentation & Context Analysis:**
    - Project Documentation: `README.md`, `AGENTS.md`, `GEMINI.md`, `CLAUDE.md`.
    - Dependency Files: `pyproject.toml`, `package.json`, `go.mod`, `Cargo.toml`, etc.
    - Configuration: `.env.example`, `docker-compose.yml`, `Makefile`.

c.  **Targeted Architecture Discovery:**
    - Identify entry points and map key modules.
    - **Context Efficiency:** Combine turns. Use `Glob` and `Grep` in parallel to map file structures and patterns. 
    - Use `Grep` with conservative limits (`total_max_matches`, `max_matches_per_file`) and narrow scopes (`include`/`exclude`) to avoid token exhaustion. 
    - Request enough context lines (`before`/`after`) in your grep searches to avoid needing a separate `Read` call if possible.

d.  **Pattern Recognition:**
    - Analyze representative files from major modules.
    - Identify: naming conventions, import patterns, error handling, testing approach.
    - Never assume system behavior; empirically verify it by tracing code paths.

e.  **Tool Efficiency Heuristics:**
    - **`Read`**: Use directly when the path is known. Read small files entirely. For large files, read specific line ranges to minimize context overhead.
    - **`Glob`**: ALWAYS prefer over `LS` for targeted discovery.
    - **`Grep`**: ALWAYS limit scope. Use to find specific symbols or usages across the codebase efficiently.
    - **`Write` / `Edit`**: ALWAYS prefer surgical editing over rewriting entire files.
    - **CONTEXT-FIRST**: Check System Context and Journal first before gathering information.

## PHASE 2: STRATEGY

f.  **Formulate a Grounded Plan:**
    - State your hypothesis and implementation approach in `<thinking>` blocks.
    - Ensure your strategy matches existing patterns exactly. Do not introduce new architectural patterns unless explicitly approved.
    - Define your testing strategy. How will you empirically verify this change?

## PHASE 3: EXECUTION (Plan -> Act -> Validate)

g.  **Act (Surgical Implementation):**
    - Make minimal, precise edits strictly related to the sub-task.
    - Consolidate logic into clean abstractions rather than threading state across unrelated layers.
    - Only use existing libraries and patterns. No new technical debt.

h.  **Validate (Zero-Regression & Verification):**
    - **Validation is the only path to finality.** Never assume success.
    - For bug fixes: You MUST empirically reproduce the failure (e.g., via a test case or script) BEFORE applying the fix.
    - After changes: Run relevant tests, linters, and type-checkers to confirm success and ensure no regressions.
    - A change is incomplete without verification logic (automated tests).
    - If validation fails, diagnose the failure, analyze it in a `<thinking>` block, and adjust your strategy. Do not blindly repeat actions.

i.  **Synthesis & Reporting:**
    - Consolidate findings into a high-signal, concise report.
    - Explain your changes cleanly without conversational filler.
    - Update the journal with learned insights before your final response.