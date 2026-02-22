---
name: core_mandate_brownfield
description: Core mandate for discovering, understanding, and modifying existing codebases safely.
user-invocable: false
---
# Skill: core_mandate_brownfield
When working in an existing repository, you MUST follow this protocol to ensure safe and successful modifications.

## PHASE 1: DISCOVERY (Before Any Modification)

a.  **High-Level Reconnaissance (Depth 2-3):**
    - Use `LS` with `depth=2` for initial structure mapping
    - Identify: source directories, test directories, configuration files, entry points
    - NEVER use `LS` if you already know specific file paths

b.  **Documentation Analysis (Priority Order):**
    1. **Project Documentation:** `README.md`, `AGENTS.md`, `CLAUDE.md` (use Project Documentation Summary if complete)
    2. **Dependency Files:** `pyproject.toml`, `requirements.txt`, `package.json`, `go.mod`, etc.
    3. **Configuration:** `.env.example`, `docker-compose.yml`, `Makefile`

c.  **Architecture Discovery:**
    - Identify entry points (`main.py`, `app.py`, `src/` structure)
    - Map key modules and their relationships
    - Use `Glob` for targeted discovery (e.g., `**/*.py` for Python files)
    - Use `Grep` for cross-file patterns (imports, class definitions, function calls)

d.  **Pattern Recognition:**
    - Analyze 2-3 representative files from each major module
    - Identify: naming conventions, import patterns, error handling, testing approach
    - Document discovered patterns in `<thinking>` blocks

e.  **Tool Efficiency Heuristics:**
    - **`Read`**: Use directly when path is known. Skip `LS` or `Glob`. Prefer reading the entire file unless it exceeds ~2000 lines.
    - **`Glob`**: ALWAYS prefer over `LS` for targeted discovery of specific file types/patterns.
    - **`Grep`**: ALWAYS use for cross-file discovery. ALWAYS limit scope via specific `regex` and `file_pattern` to minimize noise.
    - **`LS`**: Initial discovery only (depth ≤ 3). NEVER use if file name or path is known.
    - **`Write` / `Edit`**: ALWAYS prefer `Edit` for modifying existing files.
    - **`AnalyzeCode`**: VERY SLOW and token-intensive. ONLY use for complex architectural questions or cross-file flows. NEVER use if path/pattern is known.
    - **`AnalyzeFile`**: SLOW and resource-intensive. ONLY use for complex architectural questions/logic understanding. NEVER use if `Read` or `Grep` are sufficient.
    - **CONTEXT-FIRST**: Check System Context first before gathering information. Never use tools to gather information already in System Context.

## PHASE 2: EXECUTION (After Full Understanding)

f.  **Context Mastery Validation:**
    - Verify you can answer: "What are the key architectural patterns?"
    - Confirm: "What are the style conventions and dependencies?"
    - Ensure: "What tests exist and how are they run?"

g.  **Surgical Implementation:** Apply Implementation Standards:
    - Match existing patterns, style, libraries exactly
    - Make minimal, precise edits
    - Place helper functions below callers (project convention)

h.  **Zero-Regression Verification:**
    - Run existing tests BEFORE making changes (establish baseline)
    - Run tests AFTER changes (verify no regression)
    - Use project-specific test commands (see AGENTS.md)
    - ALWAYS verify changes (tests, linters, outputs) and system state after writing, editing, or executing commands with `Bash`.

i.  **No New Debt Enforcement:**
    - Only use existing libraries and patterns
    - If new patterns are needed, seek explicit approval
    - Document any deviations in `<thinking>` blocks

j.  **Synthesis & Reporting:**
    - State your hypothesis and approach in `<thinking>` blocks
    - Consolidate findings into high-signal reports
    - Update journal with learned insights before final response