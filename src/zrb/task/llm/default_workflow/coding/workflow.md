Follow this workflow to deliver high-quality, idiomatic code that respects the project's existing patterns and conventions.

# Tool Usage Guideline
- To read from multiple files, use `read_many_files` instead `read_from_file`
- Use `search_file_content` to find specific code snippets or patterns.

# Step 1: Understand the Task and Project Context

1. **Analyze the Request:** Identify what you are being asked to do. Are you writing new code, modifying existing code, or creating a script?
2. **Identify Languages (Project vs. Task):**
  - **Project Language:** Determine the language of the project by inspecting files (e.g., `pyproject.toml` -> Python, `package.json` -> JS/TS).
  - **Task Language:** Determine the language of the code you need to write.
3. **Analyze Project Conventions:** Read key project files (`README.md`, configs) and existing source code to understand the project's specific style, patterns, and tooling. **This is your highest priority.**
  - **Checklist for Analyzing Conventions:**
    - **Build System:** How is the project built? (e.g., `Makefile`, `package.json` scripts, `pom.xml`)
    - **Test Framework:** How are tests run? (e.g., `pytest`, `jest`, `go test`)
    - **Linter:** Is there a linter configured? (e.g., `ruff`, `eslint`, `golangci-lint`)
    - **Formatter:** Is there a formatter configured? (e.g., `black`, `prettier`, `go fmt`)
    - **Directory Structure:** What is the project's directory structure? (e.g., `src` layout, `cmd`/`pkg`/`internal`)

# Step 2: Read ALL Relevant Guides

Based on your analysis in Step 1, you MUST read the following guides before proceeding:

1. **The Project Language Guide:** You MUST read the guide for the **Project Language** (e.g., `python.md`) to understand its core conventions and how to interact with it (e.g., how to run its tests).
2. **The Task Language Guide:** If the **Task Language** is different from the Project Language (e.g., writing a Shell script for a Python project), you MUST also read its guide.
3. **The Git Guide:** For any task involving version control, you MUST read `git.md`.

- **CRITICAL EXAMPLE:** If asked to write a `shell` script to test a `Python` project, you must read **both** `python.md` (to understand the project's test command) and `shell.md` (to write the script correctly).

- **Guide Files:**
  - **Python:** `python.md`
  - **JavaScript/TypeScript:** `javascript.md`
  - **Go:** `golang.md`
  - **Rust:** `rust.md`
  - **Shell:** `shell.md`
  - **Git:** `git.md`
  - **Java:** `java.md`
  - **Kotlin:** `kotlin.md`
  - **Swift:** `swift.md`
  - **C#:** `csharp.md`
  - **HTML/CSS:** `html-css.md`
  - **SQL:** `sql.md`
  - **PHP:** `php.md`
  - **Ruby:** `ruby.md`
  - **C++:** `cpp.md`
  - **Ruby on Rails:** `ruby-on-rails.md`

# Step 3: Plan

Formulate a clear, step-by-step plan. Share a concise version with the user. A good plan includes:

- **Files to be modified:** A list of the files you intend to change.
- **Functions to be added or changed:** A description of the functions you will add or modify.
- **Tests to be written:** A description of the tests you will write to verify your changes.

If the session is interactive, ask for user approval first before continue.

# Step 4. Implement

**Write Code:**
- Make changes following discovered patterns
- Apply language-specific conventions from appropriate guide
- Design for testability:
  - Return values instead of printing
  - Create modular, single-responsibility functions
  - Use function arguments instead of global state

# Step 5. Verify

**Test Functionality:**
- Run existing test suite
- Add tests for new features or bug fixes
- Debug and fix any test failures

**Check Quality:**
- Run language-specific linters and formatters
- Execute build processes if applicable
- Fix any issues found

# Step 6. Finalize

- Keep all created files (including tests)
- Await user instruction for next steps
- Suggest committing changes if satisfied