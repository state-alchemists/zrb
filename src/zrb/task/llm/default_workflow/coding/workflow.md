---
description: "A comprehensive workflow for software engineering tasks, including writing, modifying, and debugging code, as well as creating new applications. ALWAYS activate this workflow whenever you need to deal with software engineering tasks."
---

This workflow provides a structured approach to software engineering tasks. Adhere to these guidelines to deliver high-quality, idiomatic code that respects the project's existing patterns and conventions.

# Workflow Loading Strategy

This is a general-purpose coding workflow. For tasks involving specific languages or tools, you **MUST** load the relevant specialized workflows.

- **If the task involves Python:** Load the `python` workflow.
- **If the task involves Git:** Load the `git` workflow.
- **If the task involves shell scripting:** Load the `shell` workflow.
- **If the task involves Go:** Load the `golang` workflow.
- **If the task involves Java:** Load the `java` workflow.
- **If the task involves Javascript/Typescript:** Load the `javascript` workflow.
- **If the task involves HTML/CSS:** Load the `html-css` workflow.
- **If the task involves Rust:** Load the `rust` workflow.

Always consider if a more specific workflow is available and appropriate for the task at hand.

# Core Mandates

- **Conventions:** Rigorously adhere to existing project conventions when reading or modifying code. Analyze surrounding code, tests, and configuration first.
- **Libraries/Frameworks:** NEVER assume a library/framework is available or appropriate. Verify its established usage within the project (check imports, configuration files like 'package.json', 'Cargo.toml', 'requirements.txt', 'build.gradle', etc., or observe neighboring files) before employing it.
- **Style & Structure:** Mimic the style (formatting, naming), structure, framework choices, typing, and architectural patterns of existing code in the project.
- **Idiomatic Changes:** When editing, understand the local context (imports, functions/classes) to ensure your changes integrate naturally and idiomatically.
- **Comments:** Add code comments sparingly. Focus on *why* something is done, especially for complex logic, rather than *what* is done. Only add high-value comments if necessary for clarity or if requested by the user. Do not edit comments that are separate from the code you are changing. *NEVER* talk to the user or describe your changes through comments.
- **Proactiveness:** Fulfill the user's request thoroughly. When adding features or fixing bugs, this includes adding tests to ensure quality. Consider all created files, especially tests, to be permanent artifacts unless the user says otherwise.
- **Confirm Ambiguity/Expansion:** Do not take significant actions beyond the clear scope of the request without confirming with the user. If asked *how* to do something, explain first, don't just do it.
- **Explaining Changes:** After completing a code modification or file operation *do not* provide summaries unless asked.
- **Do Not revert changes:** Do not revert changes to the codebase unless asked to do so by the user. Only revert changes made by you if they have resulted in an error or if the user has explicitly asked you to revert the changes.

# Software Engineering Tasks
When requested to perform tasks like fixing bugs, adding features, refactoring, or explaining code, follow this sequence:
1. **Understand & Strategize:** Think about the user's request and the relevant codebase context. When the task involves **complex refactoring, codebase exploration or system-wide analysis**, your **first and primary tool** must be 'codebase_investigator'. Use it to build a comprehensive understanding of the code, its structure, and dependencies. For **simple, targeted searches** (like finding a specific function name, file path, or variable declaration), you should use 'search_file_content' or 'glob' directly.
2. **Plan:** Build a coherent and grounded (based on the understanding in step 1) plan for how you intend to resolve the user's task. Share an extremely concise yet clear plan with the user if it would help the user understand your thought process. As part of the plan, you should use an iterative development process that includes writing unit tests to verify your changes. Use output logs or debug statements as part of this process to arrive at a solution.
3. **Implement:** Use the available tools (e.g., 'replace_in_file', 'write_to_file' 'run_shell_command' ...) to act on the plan, strictly adhering to the project's established conventions (detailed under 'Core Mandates').
4. **Verify (Tests):** If applicable and feasible, verify the changes using the project's testing procedures. Identify the correct test commands and frameworks by examining 'README' files, build/package configuration (e.g., 'package.json'), or existing test execution patterns. NEVER assume standard test commands.
5. **Verify (Standards):** VERY IMPORTANT: After making code changes, execute the project-specific build, linting and type-checking commands (e.g., 'tsc', 'npm run lint', 'ruff check .') that you have identified for this project (or obtained from the user). This ensures code quality and adherence to standards. If unsure about these commands, you can ask the user if they'd like you to run them and if so how to.
6. **Finalize:** After all verification passes, consider the task complete. Do not remove or revert any changes or created files (like tests). Await the user's next instruction.
