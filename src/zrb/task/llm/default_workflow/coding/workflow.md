When writing, refactoring, or fixing code, follow this streamlined development process for safe, high-quality contributions.

## Core Rules

- **MANDATORY:** Before any code analysis, ALWAYS consult the language-specific guide
- **Follow Conventions:** Match existing code style, structure, and patterns exactly
- **Verify Dependencies:** Never use libraries without checking project dependencies first
- **Test Before Committing:** Complete all verification steps before using version control

## Language Guides (Required Reading)

**Detect language → Read guide → Then analyze code:**
- **Python** → `./python.md`
- **JavaScript/TypeScript** → `./javascript.md`
- **Go** → `./golang.md`
- **Rust** → `./rust.md`
- **Git Commands** → `./git.md`
- **Shell Scripts** → `./shell.md`

**Priority:** Always prioritize existing project style over general language conventions.

## Development Process

### 1. Understand & Plan

**Language Setup (Required First Step):**
- Identify primary language from project files
- **Read corresponding language guide**
- Apply language conventions as baseline

**Gather Context:**
- Analyze requirements and break them into concrete tasks
- Explore codebase to identify relevant files and understand conventions
- Check for existing tests and configuration files
- Verify any needed dependencies are already in the project

**Create Plan:**
- Formulate step-by-step implementation strategy
- Share concise plan summary with user for alignment

### 2. Implement

**Write Code:**
- Make changes following discovered patterns
- Apply language-specific conventions from appropriate guide
- Design for testability:
  - Return values instead of printing
  - Create modular, single-responsibility functions
  - Use function arguments instead of global state

### 3. Verify

**Test Functionality:**
- Run existing test suite
- Add tests for new features or bug fixes
- Debug and fix any test failures

**Check Quality:**
- Run language-specific linters and formatters
- Execute build processes if applicable
- Fix any issues found

### 4. Finalize

- Keep all created files (including tests)
- Await user instruction for next steps
- Suggest committing changes if satisfied