🔖 [Documentation Home](../README.md)

## 1.21.43

- **Improvement: LLM Chat Responsiveness**:
  - **Responsive ESC Handler**: Enhanced the interrupt handling in `llm-chat` to be more responsive, ensuring immediate cancellation of tasks when the `ESC` key is pressed.
- **Performance**:
  - **Lazy Loading**: Implemented lazy loading for `requests` module and optimized `asyncio.sleep` wait times to improve startup performance and responsiveness.

## 1.21.0 (November 19, 2025)

This release summarizes the cumulative changes across the 1.1–1.21 line since 1.0.0 — roughly nine months of v1 evolution, dominated by a major build-out of the LLM/agent subsystem alongside web-UI, scaffolding, and task-engine improvements.

- **Feature: LLM agent tooling and built-in toolset**:
  - Added a rich set of agent-callable tools, including file operations, a code analysis/edit toolset (`replace_in_file`, repo/file analysis), web tools, RAG, and note-taking tools.
  - Replaced `apply_diff` with `replace_in_file`, refreshed tool docstrings, and made the default toolset configurable.
  - Added sub-agent delegation and a SearXNG-backed search integration (with Brave engine and `exclude-from` support).

- **Feature: Conversation history, context, and summarization**:
  - Introduced a conversation-history class with conversation context carried through history.
  - Refactored LLM context and history management, made summarization and context enrichment more robust, moved them into the system prompt, and added faster token calculation via tiktoken.

- **Feature: MCP and model configuration**:
  - Added an MCP servers parameter for `LLMTask`, later moving to a toolset-based integration and supporting `mcp-config.json` loading.
  - Introduced `llm_config` with default model settings, a configurable "small" model, YOLO/non-interactive modes, and workflow configuration; removed the explicit `Agent` parameter from `LLMTask`.

- **Feature: LLM workflows and prompt system overhaul**:
  - Added configurable LLM workflows, including language-specific coding guides (e.g. shell, Rust) and custom built-in workflows.
  - Extensively restructured and refined the default system prompts (persona, interactive, file/repo extractor, summarization) for clarity and better tool-confirmation behavior.

- **Feature: Interactive chat experience**:
  - Made `llm-chat` continuous and reworked `llm-chat`/`llm-ask`, adding chat sessions, chat triggers, attachments, and interactive prompting via a lazily-imported `prompt_toolkit`.
  - Improved CLI streaming, markdown styling, and output clipping.

- **Feature: New built-in tasks and tools**:
  - Added utility tasks/tools for `base64`, `md5`, `uuid`, `jwt`, and HTTP requests, plus the ability to remove tasks or groups.

- **Improvement: Web UI, CRUD, and FastApp scaffolding**:
  - Integrated an HTML modifier and reworked CRUD scaffolding, adding user and role CRUD with GUI, refreshed auth (user/role/permission) views, and updated repositories/services and Pico CSS assets.

- **Improvement: Task engine and configuration**:
  - Refactored `BaseTask` and `LLMTask`, added task-to-function conversion, improved input handling, added `is_web_mode`/`is_tty` context, configurable banner, and `shared_ctx` input on `BaseTrigger`.
  - Reworked the config system to be more lazy-loaded and added new config options across LLM, web, and search.

- **Improvement: Performance and startup**:
  - Made OpenAI, pydantic-ai, `prompt_toolkit`, and analysis paths lazily imported to speed up startup, alongside broader lazy-load refactoring.

- **Fixes**: Resolved scheduled-task and Rsync task bugs, git subtree handling, YOLO kwargs rendering, CLI/streaming and newline logging issues, MCP function-name labeling, XCom `NoneType` errors, multiline-mode triggering on `\n`, and `analyze_repo`/`analyze_file` bugs; expanded test coverage throughout.

## 1.0.0 (February 23, 2025)

Version 1.0.0 is a complete ground-up rewrite ("New Beginning") that supersedes the entire 0.x YAML-based line. Tasks are now defined in pure Python, and the project pivots from a YAML-configured task runner into a full automation platform with a web server, LLM agent, and code generators.

- **Rewrite: Pure-Python core ("New Beginning")**:
  - Replaced the 0.x YAML/`ruamel.yaml`/`jsons` task definition model with pure-Python task objects, removing the legacy DSL entirely.
  - Restructured `src/zrb/` into focused modules (`task/`, `runner/`, `session/`, `context/`, `util/`, `xcom/`, `config.py`) with a new `BaseTask` engine.
  - Overhauled dependencies: dropped `click`, `beartype`, `jsons`, `ruamel.yaml`, `termcolor`, `croniter`; added FastAPI, `pydantic-ai`, `fastembed`, `chromadb`/`pdfplumber` (RAG extra), `python-jose`, `ulid-py`, `psutil`, and `sqlmodel`/`alembic` for generated apps.

- **Task Engine: Redesigned execution model**:
  - New `BaseTask`/`Task`/`CmdTask` hierarchy with DAG-based dependencies, skip/readiness mechanisms, XCom for inter-task data, and structured input/env handling.
  - Added a `Scheduler`/`BaseTrigger` model with cron support, plus `RsyncTask` and remote command capability for `CmdTask`.
  - Introduced `Scaffolder`/content transformers and a `libcst`-based `codemod` toolkit for programmatic code generation and modification.

- **Web UI & Server: Browser-based runner**:
  - Added a FastAPI web server that runs tasks from the browser with dynamic per-task input forms, multiline/text inputs, action buttons, and live session monitoring/polling.
  - Added session state logging/reading (`SessionStateLogger`), session listing APIs, autoloading, and CLI-only task gating.
  - Added authentication (login/logout pages, JWT via `python-jose`), navigation, permissions, and a Dockerfile for deployment.

- **LLM Integration: Built-in AI agent**:
  - Added an `LLMTask` and `zrb llm chat` command backed by `pydantic-ai`, with async execution, tool calling, and a max-iteration guard (migrated off an initial LiteLLM integration).
  - Added agent tools for CLI, web, and API access, plus RAG over documents using `fastembed` embeddings and `chromadb` (`-E rag` extra, supporting PDF ingestion).
  - Integrated and superseded the former `zrb-ollama` capabilities into the core LLM task.

- **Generators & Scaffolding: FastApp generator**:
  - Added `zrb project add fastapp` to scaffold a FastAPI application with monorepo/microservices support, module and entity/CRUD generators, and gateway routing.
  - Generated apps ship auth (users, roles, permissions, sessions/tokens), Alembic migrations, SQLModel repositories/services, API clients with sort/filter/`MultiResponse`, and HTML views.

- **CLI & Built-ins: New surface**:
  - New entry point (`zrb` via `serve_cli`) with dynamic autocompletion, restyled CLI graphics/banner, and ergonomic logging output.
  - Rebuilt built-in task groups: `git`/`git_subtree`, `python`, `base64`, `md5`, `random`, `project`, `setup`, `shell`, `llm`, and an expanded `todo` toolkit (add/list/show/archive, filtering, status color-coding, custom headers, responsive output).

- **Removed: Legacy 0.x surface**:
  - Removed the YAML configuration layer and the `devtool install` suite (aws, gcloud, docker, helm, kubectl, pulumi, terraform, selenium, pyenv, nvm, gvm, sdkman, zsh, tmux, helix) along with the old `task_input/` classes and `action/runner.py`.

🔖 [Home](../../../README.md) > [Documentation](../../README.md) > [Changelog v1](README.md)
