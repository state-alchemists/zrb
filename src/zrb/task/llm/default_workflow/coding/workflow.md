---
description: "A general-purpose workflow for writing, modifying, and debugging code."
---
Follow this workflow to deliver high-quality, idiomatic code that respects the project's existing patterns and conventions.

# Core Mandates

- **Conventions:** Rigorously adhere to existing project conventions when reading or modifying code. Analyze surrounding code, tests, and configuration first.
- **Libraries/Frameworks:** NEVER assume a library/framework is available or appropriate. Verify its established usage within the project (check imports, configuration files like 'package.json', 'Cargo.toml', 'requirements.txt', 'build.gradle', etc., or observe neighboring files) before employing it.
- **Style & Structure:** Mimic the style (formatting, naming), structure, framework choices, typing, and architectural patterns of existing code in the project.
- **Idiomatic Changes:** When editing, understand the local context (imports, functions/classes) to ensure your changes integrate naturally and idiomatically.
- **Comments:** Add code comments sparingly. Focus on why something is done, especially for complex logic, rather than what is done. Only add high-value comments if necessary for clarity or if requested by the user. Do not edit comments that are separate from the code you are changing. NEVER talk to the user or describe your changes through comments.
- **Proactiveness:** Fulfill the user's request thoroughly. When adding features or fixing bugs, this includes adding tests to ensure quality. Consider all created files, especially tests, to be permanent artifacts unless the user says otherwise.

# Tool Usage Guideline
- To read from multiple files, use `read_from_file` with a list of paths
- Use `search_files` to find specific code snippets or patterns

# Step 1: Understand the Task and Project Context

1. **Analyze the Request:** Identify what you are being asked to do. Are you writing new code, modifying existing code, or creating a script?
2. **Identify Languages (Project vs. Task):**
  - **Project Language:** Determine the language of the project by inspecting files (e.g., build configuration files, dependency files).
  - **Task Language:** Determine the language of the code you need to write.
3. **Analyze Project Conventions:** Read key project files (`README.md`, configs) and existing source code to understand the project's specific style, patterns, and tooling. **This is your highest priority.**
  - **Checklist for Analyzing Conventions:**
    - **Build System:** How is the project built? (e.g., `Makefile`, build scripts)
    - **Test Framework:** How are tests run?
    - **Linter:** Is there a linter configured?
    - **Formatter:** Is there a formatter configured?
    - **Directory Structure:** What is the project's directory structure?

# Step 2: Plan

Formulate a clear, step-by-step plan. Share a concise version with the user. A good plan includes:

- **Files to be modified:** A list of the files you intend to change.
- **Functions to be added or changed:** A description of the functions you will add or modify.
- **Tests to be written:** A description of the tests you will write to verify your changes.

If the session is interactive, ask for user approval first before continue.

# Step 3: Implement

**Write Code:**
- Make changes following discovered patterns
- Apply language-specific conventions from appropriate guide
- Design for testability:
  - Return values instead of printing
  - Create modular, single-responsibility functions
  - Use function arguments instead of global state

# Step 4: Verify

**Test Functionality:**
- Run existing test suite
- Add tests for new features or bug fixes
- Debug and fix any test failures

**Check Quality:**
- Run language-specific linters and formatters
- Execute build processes if applicable
- Fix any issues found

# Step 5: Finalize

- Keep all created files (including tests)
- Await user instruction for next steps
- Suggest committing changes if satisfied