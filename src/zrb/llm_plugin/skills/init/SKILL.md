---
name: init
description: Initialize a project for AI-assisted development. Generates AGENTS.md (universal AI guide) through systematic codebase analysis. Use when setting up a new project or when no AI guidance files exist yet.
disable-model-invocation: true
user-invocable: true
---
# Skill: init

When this skill is activated, you perform a systematic codebase analysis and generate `AGENTS.md` — a universal AI assistant guide that works with any LLM (Claude, Gemini, GPT, etc.). Always present the proposed content to the user for approval before writing.

---

## Phase 1: Codebase Analysis

Gather facts — do not guess. Every claim in `AGENTS.md` must come from something you read.

### 1a — Project Structure

```
LS .          # top-level overview
LS src/       # if src/ exists
```

Note: main source directories, test directories, config directories.

### 1b — Identify Build System and Language

Read whichever of these exist (use `ReadMany`):

| File | What it reveals |
|------|----------------|
| `pyproject.toml` / `setup.py` / `setup.cfg` | Python project, deps, scripts |
| `package.json` | Node.js project, scripts (build/test/lint), deps |
| `go.mod` | Go project, module name, Go version |
| `Cargo.toml` | Rust project |
| `pom.xml` / `build.gradle` | Java/Kotlin project |
| `Makefile` | Build targets — read ALL targets |
| `tox.ini` / `pytest.ini` / `.pytest.ini` | Python test config |
| `jest.config.*` / `vitest.config.*` | JS test config |
| `.github/workflows/*.yml` | CI pipeline — reveals the canonical test/build commands |
| `Dockerfile` | Runtime environment |
| `.env.example` / `template.env` | Required environment variables |

### 1c — Extract Exact Commands

From what you read, extract the **exact** commands for:
- **Install**: how to install dependencies
- **Build**: how to compile or bundle
- **Test**: how to run the test suite, including required flags (e.g., `--watch=false`)
- **Lint**: linter command and config
- **Format**: formatter command
- **Run (dev)**: how to start the project locally

If multiple options exist (e.g., `make test` and `pytest`), list both and note which is preferred.

### 1d — Architecture Discovery

```
Glob src/**/*.py   # or the relevant extension
```

Read `README.md` if it exists. Read 2-3 representative source files to understand:
- Entry points (main files, app factories, CLI entrypoints)
- Key abstractions (core classes, interfaces, domain models)
- Module organization pattern (feature-based, layer-based, etc.)

### 1e — Convention Extraction

From reading actual code, extract:
- Naming conventions (snake_case, camelCase, PascalCase)
- File/module naming patterns
- Import style (relative vs absolute)
- Test file naming and location (`test_*.py`, `*.test.ts`, `*_test.go`)
- Error handling patterns
- Where shared utilities live

---

## Phase 2: Generate AGENTS.md

Produce the full content and present it to the user before writing.

```markdown
# [Project Name]

## Overview

[1-2 sentences: what this project does and who uses it.]

## Essential Commands

\`\`\`bash
# Install dependencies
[exact command]

# Build
[exact command, or omit section if interpreted language with no build step]

# Run tests
[exact command with required flags, e.g.: pytest --tb=short -x]

# Lint
[exact command]

# Format
[exact command]

# Start dev server / run locally
[exact command]
\`\`\`

## Architecture

[2-4 sentences describing the high-level structure and key design decisions.]

| Directory / File | Purpose |
|-----------------|---------|
| `[main source dir]/` | [what lives here] |
| `tests/` | [test structure and framework] |
| `[key config file]` | [what it configures] |

## Development Guidelines

- **Before modifying a module**, read it and its tests together.
- **Test framework**: [name]. Tests live in `[location]`. Run with `[exact command]`.
- **Naming**: [conventions from Phase 1].
- **Imports**: [relative/absolute pattern observed in the code].
- **Error handling**: [pattern used in the project].

## Important Constraints

[Things an AI assistant must not do — inferred from the codebase. Only include if evidence exists:]
- e.g., "Do not use `os.system` — use `subprocess` with explicit args instead."
- e.g., "All database access goes through the repository layer — never query the DB directly from a handler."
- e.g., "Do not commit `.env` — use `template.env` as the reference."

## Key Files

| File | Purpose |
|------|---------|
| [file path] | [what it is and why an AI working on this project should know about it] |
```

---

## Phase 3: Present and Write

1. Show the proposed `AGENTS.md` to the user.
2. Ask for confirmation or changes before writing.
3. Write the approved file using `Write` to `AGENTS.md` in the project root.
4. Remind the user: commit `AGENTS.md` to version control so all AI tools on this project benefit from it.
