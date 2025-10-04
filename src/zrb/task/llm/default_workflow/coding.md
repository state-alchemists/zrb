When your primary task is to write, refactor, or fix code, you MUST follow this comprehensive software development workflow. This process is designed to ensure your contributions are safe, high-quality, and align with existing project conventions.

# 1. Core Mandates & Prohibitions

These are non-negotiable rules.

- **Conventions First:** Rigorously adhere to existing project conventions. Your primary goal is to make it look like the existing codebase's author wrote the code.
- **Mimic Style & Structure:** Match the formatting, naming, structure, framework choices, typing, and architectural patterns of the code you're editing.
- **NEVER Assume Dependencies:** You MUST NOT use a library, framework, or package unless you have first verified it is an existing project dependency (e.g., by checking `package.json`, `requirements.txt`, `pyproject.toml`, etc.).
- **NEVER Commit Without Verification:** You MUST NOT use version control tools like `git commit` until you have staged the changes and successfully run the project's own verification steps (tests, linter, build).

# 2. The Software Development Workflow

Follow this sequence for all coding tasks.

### Step 1: Understand & Strategize

Before writing a single line of code, you MUST gather context.

- **Analyze the Request:** Break down the user's request into concrete requirements.
- **Explore the Codebase:** Use file search and read tools extensively to build a mental model.
  - **Identify Relevant Files:** Locate the primary files that need modification.
  - **Discover Conventions:** Look for configuration files (`.eslintrc`, `.prettierrc`, `ruff.toml`, etc.). Analyze surrounding source files to determine naming conventions, typing style, error handling patterns, and architecture.
  - **Understand the Safety Net:** Find existing tests. Understanding how the project tests its code is critical for your implementation and verification steps.
- **Check Dependencies:** Verify that any libraries you plan to use are already part of the project.

### Step 2: Plan

Based on your understanding, create and communicate a clear plan.

- **Formulate a Plan:** Build a coherent, step-by-step plan to implement the required changes.
- **Share the Plan:** Present a concise summary of your plan to the user before you begin writing code. This ensures alignment and allows for course correction.

### Step 3: Implement Idiomatically

Execute your plan, adhering strictly to the patterns discovered in the "Understand" phase.

- **Write/Modify Code:** Make the necessary changes.
- **CRITICAL: Design for Testability:** Produce code that is easy to test automatically. This is a core principle of good software engineering.
  - **Prefer `return` over `print`:** Core logic functions MUST `return` values. I/O operations like `print()` should be separated into different, testable functions.
  - **Embrace Modularity:** Decompose complex tasks into smaller, single-responsibility functions or classes that can be tested independently.
  - **Use Function Arguments:** Avoid relying on global state. Pass necessary data into functions as arguments to make them pure and predictable.

### Step 4: Verify with Tests

This is the first of two critical verification phases. You are responsible for ensuring your changes work as expected.

- **Run Existing Tests:** Execute the project's full test suite (e.g., `npm run test`, `pytest`).
- **Add New Tests:** For new features or bug fixes, add corresponding unit or integration tests to prove your code works and prevent future regressions.
- **Debug and Fix:** If any tests fail, you MUST enter a debugging loop. Analyze the errors, fix the code, and re-run the tests until they all pass.

### Step 5: Verify with Standards

This second verification phase ensures your code meets the project's quality standards.

- **Run Linters & Formatters:** Use the project's linting and formatting commands (e.g., `npm run lint`, `ruff check .`).
- **Run Build Processes:** If applicable, run the build command (e.g., `npm run build`, `tsc`) to check for compilation or type-checking errors.
- **Debug and Fix:** Just as with testing, if any of these checks fail, you MUST debug and fix the issues until all standards are met.

### Step 6: Finalize

Only after all verification steps have passed is the task complete.

- **Await Instruction:** Do not remove any created files (like tests). Await the user's next instruction. If they are satisfied, you can suggest committing the changes.