🔖 [Home](../../README.md) > [Documentation](../README.md) > [Changelog](README.md)

# 1.21.6

- **Refactor**: Significant refactoring of prompt construction logic and related utilities.
  - Added `get_contexts` method in `src/zrb/config/llm_context/config.py`.
  - Refactored prompt construction logic in `src/zrb/task/llm/prompt.py` for persona, system prompts, special instructions, and workflows.
  - Minor adjustments to `src/zrb/util/markdown.py` for markdown section content stripping.
- **Improved**: Docstring verbosity for LLM tools.
  - Docstrings updated across `src/zrb/builtin/llm/tool/api.py`, `src/zrb/builtin/llm/tool/cli.py`, `src/zrb/builtin/llm/tool/code.py`, `src/zrb/builtin/llm/tool/file.py`, `src/zrb/builtin/llm/tool/note.py`, `src/zrb/builtin/llm/tool/web.py`.
- **Updated dependencies**:
  - `pydantic-ai-slim` `~1.24.0`
  - `requests` `^2.32.5`
  - `tiktoken` `^0.12.0`
  - `markdownify` `^1.2.2`
  - `playwright` `^1.56.0` (optional)
  - `chromadb` `^1.3.5` (optional)

# 1.21.5

- **Changed**: Tools docstring has been updated to be more verbose.


# 1.21.4

- **Added: Write mode**
  - Add write mode to `write_to_file` so that when the LLM failed to write to file, it can break down the content to smaller pieces and write with `a` (append) mode.


# 1.21.3

- **Improvement**
  - Use `NotRequired` to make the `TypedDict`'s property on file tools fully optional.
  - Introduce `ShellCommandResult` `TypedDict`
  - Improve `/run` command output.


# 1.21.2

- **Update dependencies**: pydantic-ai-slim `1.22.0`.
- **Changed** Other AI provider except OpenAI is now not installed by default.

# 1.21.1

- **Fix: LLM Chat Parameter Editing**:
  - Fixed bug where editing parameters without specifying a key in LLM chat sessions was not working correctly.
  - Improved parameter editing flow to properly handle empty keys and merge dictionary values.
  - Removed debug print statements from the parameter editing logic.

# 1.21.0

- **Feature: Enhanced Prompt System**:
  - Updated system prompts and interactive prompts for better clarity and workflow guidance.
  - Enhanced all default workflows (coding, copywriting, git, golang, html-css, java, javascript, python, researching, rust, shell) with improved instructions and examples.
  - Improved tool documentation and parameter handling across all LLM tools.
  - Added comprehensive YAML utility functions for better parameter parsing and editing.

# 1.20.1

- **Fix: Shell Autocompletion Customization**:
  - Fixed Bash and Zsh autocompletion scripts to respect the configured root group name (`CFG.ROOT_GROUP_NAME`) instead of hardcoding "zrb".
  - Updated autocompletion task signatures to use `AnyContext` instead of `Context` for better type consistency.
- **Refactor: Type Annotation Improvements**:
  - Removed unused `AnySharedContext` import from `make_task.py`.
  - Updated `make_task` function to return `AnyTask` type annotation for better type safety.

# 1.20.0

- **Feature: Enhanced Chat Session Commands**:
  - Refactored chat session commands into a dedicated `chat_session_cmd.py` module for better organization and maintainability.
  - Added new `/run <cli-command>` command to execute non-interactive shell commands directly from the chat session.
  - Enhanced workflow and attachment management with subcommands:
    - `/workflow add <workflow>` - Add a workflow to active workflows
    - `/workflow set <workflow1,workflow2,...>` - Set active workflows
    - `/workflow clear` - Deactivate all workflows
    - `/attachment add <attachment>` - Add a file attachment
    - `/attachment set <attachment1,attachment2,...>` - Set attachments
    - `/attachment clear` - Clear all attachments
  - Improved command matching system with support for multiple command aliases and subcommands.
- **Feature: Improved System Prompts**:
  - Enhanced both interactive and standard system prompts with explicit workflow loading requirements.
  - Added "Load Relevant Workflows" as the first step in both workflows to ensure proper workflow initialization.
  - Improved workflow section formatting with clearer distinction between active and available workflows.
- **Refactor: Markdown Utility Renaming**:
  - Renamed `make_prompt_section` utility to `make_markdown_section` for better clarity and consistency.
  - Moved markdown utilities from `src/zrb/util/llm/prompt.py` to `src/zrb/util/markdown.py`.
  - Updated all references across the codebase to use the new naming convention.
- **Improved: Directory Tree Generation**:
  - Enhanced directory tree generation to exclude hidden files by default for cleaner output.
  - Added proper child counting to respect the `max_children` limit accurately.
- **Removed: Token Usage Display**:
  - Removed token counter from user message context to reduce clutter and improve performance.

# 1.19.0

- **Changed** Remove `read_many_files`.

# 1.18.11

- **Fix** Fix `get_workflow_name` parameter.

# 1.18.10

- **Fix** Remove invalid property from `LLMWorkflow`.

# 1.18.9

- **Feature: Enhanced LLM Chat Session**:
  - Added `/save <file-path>` command to save the last response to a file.
  - Improved command formatting in help display for better readability.
- **Refactor: write_file**: Ensure to expanduser before checking and creating directory.

# 1.18.8

- **Feature:** New attachment interface for `llm_ask` and `llm_chat`
- **Refactor: Simplify llm_ask user handling logic**

# 1.18.7

- **Changed:** Separate active and inactive workflow on system prompt.

# 1.18.6

- **Updated:** Update pydantic AI to `1.12.0`.

# 1.18.5

- **Changed:** workflow part on system prompt is now a bit shorter.

# 1.18.4

- **Refactor: Split Coding Workflow into several workflows**
- **Feature:** `load_workflow` is now accepting list as well.

# 1.18.3

- **Feature: Enhanced Analysis Tools**:
  - Improved `analyze_repo` and `analyze_file` tools with better parameter naming (`goal` → `query`) and enhanced documentation for more effective codebase analysis.
  - Added YAML metadata support for workflow descriptions in `LLMWorkflow` class.
- **Feature: New Workflow Management**:
  - Introduced `load_workflow` tool for dynamic workflow loading during LLM sessions.
  - Enhanced workflow discovery with support for both `workflow.md` and `SKILL.md` files.
  - Improved workflow display with better descriptions and metadata extraction.
- **Feature: Enhanced Reference Handling**:
  - Improved file and directory reference formatting in user messages for better clarity.
- **Dependency**: Added `pyyaml` dependency for YAML metadata parsing in workflows.

# 1.18.2

- **Fix:** Fixing `RsyncTask`'s `exclude-from` parameter parsing.

# 1.18.1

- **Feature:** Improve default workflows

# 1.18.0

- **Feature: LLM Workflow Refactoring**:
  - Replaced the concept of "modes" with "workflows" for a more structured and intuitive experience.
  - Workflows now support a directory-based structure with a `workflow.md` file, allowing for better organization and management.
  - Added new language-specific workflow guides for Python, JavaScript/TypeScript, Go, Rust, Git, and Shell to provide tailored development support.
- **Feature: Enhanced Tool Execution**:
  - Implemented `SIGINT` (Ctrl+C) handling in the tool wrapper to ensure graceful interruption of tool execution without terminating the program.
  - Improved the output of `write_to_file` and `replace_in_file` tools to be more user-friendly and informative.
- **Fixed: System Prompt Handling in LLM Task**:
  - Internally, use `instructions` instead of `system_prompts` because of [this issue](https://github.com/pydantic/pydantic-ai/issues/1032)
- **Refactor: Rsync Task Improvement**:
  - Adjusted the `rsync` command to include a space before the source and destination paths for better command-line compatibility.
- **Testing**:
  - Updated tests for `write_to_file`, `replace_in_file`, and `llm_context_config` to align with the latest changes and ensure continued stability.

# 1.17.4

- **Feature: Enhanced Search Engine Support**: Added Brave Search API integration as an alternative search method with configurable language and safe search settings.
- **Feature: Improved RsyncTask**: Added `exclude-from` parameter support for more flexible file synchronization patterns.
- **Improved: Search Engine Configuration**: Enhanced all search engines (SerpAPI, Brave, SearXNG) with configurable language and safe search parameters.
- **Fixed: Type Annotation Issues**: Corrected type annotations in RsyncTask and utility functions for better type safety.
- **Refactor: Utility Function Fix**: Fixed `get_str_list_attr` function to return a list instead of a set for consistent behavior.

# 1.17.3

- **Feature: Enhanced Token Management**: Added `LLM_MAX_TOKENS_PER_TOOL_CALL_RESULT` configuration to limit tool call result sizes and prevent excessive token usage.
- **Improved: Rate Limiter Enhancements**: Enhanced the `LLMRateLimiter` with better token counting, prompt clipping, and JSON handling capabilities.
- **Documentation: Enhanced Tool Documentation**: Added more detailed documentation for `run_shell_command` about running background processes.
- **Security: Tool Result Validation**: Added automatic validation of tool call result sizes to prevent token overflow.
- **Refactor: Prompt System Improvements**: Refactored prompt construction logic for better maintainability and token usage tracking.

# 1.17.2

- **Changed: Rename Convesation Context to Conversation Environment** A better diction, hopefully help LLM distinguish context and environment.
- **Added: Maximum Item for Directory Tree Display** Make sure to not overwhelm LLM with too much context.

# 1.17.1

- **Feature: Enhanced Context Awareness**: Added directory tree display (depth=2) to conversation context for better project structure visibility.
- **Improved Documentation**: Updated docstrings for LLM file system tools (`list_files`, `read_from_file`, `write_to_file`, `replace_in_file`) and note tools (`read_long_term_note`, `write_long_term_note`, `read_contextual_note`, `write_contextual_note`) for better clarity and consistency.
- **Enhanced Tool Execution Messages**: Improved user feedback messages for tool execution, including clearer cancellation and parameter update notifications.
- **Publishing Enhancement**: Added `--skip-existing` flag to pip publishing command to prevent errors when publishing existing versions.

# 1.17.0

- **Feature: SearXNG Integration**: Added support for SearXNG as a local, privacy-respecting alternative to SerpAPI for internet searches.
  - New configuration variables: `ZRB_SEARCH_INTERNET_METHOD`, `ZRB_SEARXNG_PORT`, `ZRB_SEARXNG_BASE_URL`.
- **Feature: Customizable LLM Tools**: `get_current_location`, `get_current_weather`, and `search_internet` can now be customized through factory functions in `LLMConfig`.
- **Breaking Change**: Removed `search_wikipedia` and `search_arxiv` tools.
- **Deprecated**: The `is_yolo_mode` parameter in `LLMTask` is deprecated. Use `yolo_mode` instead.

# 1.16.5

- **Fixed**: Correct function name (in approval/confirmation flow) when using MCP

# 1.16.4

- **Feature: Note Taking Tool**: Introduced a new `note` tool that allows the AI agent to manage long-term and contextual notes, improving its ability to recall information across sessions.
- **Feature: User Interception of Tool Calls**: The system now notified about users parameters edit of a tool call before it is executed.
- **Refactor: Simplified History Summarization**: The history summarization process has been streamlined. It no longer handles note-taking, which is now managed by the dedicated `note` tool.
- **Docs: Enhanced Tool and Workflow Documentation**:
  - The documentation for file system tools (`list_files`, `read_from_file`, `read_many_files`) has been updated to clarify the handling of line numbers and encourage robust file path discovery.
  - The domain-specific workflow for coding tasks has been significantly expanded to provide a more comprehensive and structured development process.
- **Testing**:
  - Added unit tests for the new `note` tool to ensure its reliability.
  - Updated the end-to-end test script (`zrb-test-llm-chat.sh`) to use the `llm-ask` command, aligning with the latest changes.

# 1.16.3

- **Added**: Introduce `llm_chat_trigger`
- **Fixed**: Several minor bug fixes

# 1.16.2

- **Dependencies**: Rolled back the version of several dependencies in `poetry.lock`, including `cohere`, `mistralai`, `openai`, and `pydantic-ai-slim`.
- **Refactor**: Simplified `read_user_prompt` in `chat_session.py` for better readability and removed unnecessary condition checks.
- **Cleanup**: Removed unused imports and methods from several modules including `llm_ask.py` and `tool_wrapper.py`.
- **Bug Fixes**: Corrected logic in `base/execution.py` and adjusted task monitoring checks in `base/monitoring.py` for task readiness.

# 1.16.1

- **Added** `xmltodict` for arxiv tool
- **Fixed** `--start-new` handling for llm-chat

# 1.16.0

- **Breaking Change**: Many LLM tools now return a dictionary (`dict[str, Any]`) instead of a JSON string for more structured output. This affects `run_shell_command`, `list_files`, `read_from_file`, `write_to_file`, `search_files`, `replace_in_file`, `analyze_file`, `read_many_files`, `write_many_files`, `open_web_page`, `search_internet`, `search_wikipedia`, `search_arxiv`, and sub-agent tools.
- **Feature**: Introduced a new `Context` section in `ZRB.md` for cascading context, distinct from `Note` sections.
- **Refactor**: The `llm-chat` command has been refactored for better user experience.
- **Docs**: Updated documentation to reflect the new `Context` feature and other changes.
- **Tests**: Increased test coverage for `zrb.config.llm_context.config` from 87% to 96%.

# 1.15.27

- **Changed** Not creating `./ZRB.md` if the file is not exists, instead try to use/create `~/ZRB.md`.

# 1.15.26

- **Added** Confirmation for MCP tools

# 1.15.25

- **Fixed** Make sure most configuration can be overridden with `zrb_init.py` by definine environment variable value.
- **Changed** `builtin` will always be imported.

# 1.15.24

- **Updated** Use [output function](https://ai.pydantic.dev/output/#output-functions) for summarization.

# 1.15.23

- **Fixed** Chose emojis with good visibilities on terminal
- **Updated** Pydantic AI to 1.0.1

# 1.15.22

- **Added** Capability to edit LLM tool call parameter

# 1.15.21

- **Removed** `_dummy` tool parameter is no longer needed.
- **Changed** Use dictionary input instead of json string.

# 1.15.20

- **Fixed** Yolo mode input value

# 1.15.19

- **Changed** Allows list of tool (comma separated) as `ZRB_LLM_YOLO_MODE` value.

# 1.15.18

- **Feature**: YOLO mode can now be a list of tool names to allow selective tool execution without confirmation.
- **Feature**: Tasks can now be converted to Python functions using the `to_function()` method.
- **Changed**: Upgraded `pydantic-ai` dependency, replacing `OpenAIModel` with `OpenAIChatModel`.
- **Fixed**: Minor bug fixes and refactoring.

# 1.15.17

- **Fixed** Promptoolkit user input

# 1.15.16

- **Changed** On tty mode, use promptollkit to read user input

# 1.15.15

- **Changed** Update summarizer prompt again
- **Changed** Update pydantic ai to 0.8.0

# 1.15.4

- **Fixed** Add request header at wikipedia/arxiv tool

# 1.15.13

- **Fixed** Ensure relative path when writing context to `ZRB.md`
- **Changed** Make summarizer prompt easier

# 1.15.12

- **Changed** Fix summarization prompt again
- **Changed** Renamed `UserDisapprovalError` to `ToolExecutionCancelled`

# 1.15.11

- **Added** Introduce `UserDisapprovalError`
- **Changed** Make sure summarization prompt final response

# 1.15.10

- **Fixed** More clear summarization prompt, make sure no loop happening with gemini-pro model
- **Changed** Increase pydantic-ai-slim version

# 1.15.9

- **Changed** Remove debugging log

# 1.15.8

- **Improved** default prompts

# 1.15.7

- **Fixed** Add handler for `UnexpectedModelBehavior`

# 1.15.6

- **Features**:
  - Added `ZRB_USE_TIKTOKEN` and `ZRB_TIKTOKEN_ENCODING` environment variables for more control over token counting.
- **Changed**:
  - Improved the tool confirmation prompt for better readability.
  - Updated various dependencies.
  - Refactored the `LLMRateLimiter` to use `tiktoken` more efficiently.
  - Update envvar in docs (e.g., `ZRB_LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD` to `ZRB_LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_LIMIT`).
- **Fixes**:
  - Fixed an issue where a sub-agent failing would not raise an exception.
  - Corrected the default values for `LLM_MAX_REQUESTS_PER_MINUTE` and `LLM_MAX_TOKENS_PER_REQUEST`.

# 1.15.5

- **Changed** Make tool confirmation in-line

# 1.15.4

- **Changed** Better tool confirmation

# 1.15.3

- **Changed** Fix llm task logging

# 1.15.2

- **Fixed** Workflow cascading logic

# 1.15.1

- **Fixed** Workflow load is now case insensitive

# 1.15.0

- **Added** Introduce `remove_task` and `remove_group` to `AnyGroup` and `Group`.
- **Feature: Granular File and Repo Analysis Control**:
  - Introduced `analyze_repo` and `analyze_file` as optional tools for the LLM.
  - Added new environment variables to control their availability:
    - `ZRB_LLM_ALLOW_ANALYZE_REPO`: Enables the `analyze_repo` tool.
    - `ZRB_LLM_ALLOW_ANALYZE_FILE`: Enables the `analyze_file` tool.
- **Changed: Configuration Renaming for Clarity**:
  - Renamed `ZRB_LLM_ACCESS_LOCAL_FILE` to `ZRB_LLM_ALLOW_ACCESS_LOCAL_FILE`.
  - Renamed `ZRB_LLM_ACCESS_SHELL` to `ZRB_LLM_ALLOW_ACCESS_SHELL`.
- **Changed: Default Model Update**:
  - The default LLM is now `openai:gpt-4o`.

# 1.14.8

- **Changed** Make beautifulsoup lazy-loaded.

# 1.14.6

- **Temporarily Fixed** Limitting OpenAi's library version.
- **Added** New environment variable `_ZRB_ENV_PREFIX` to make white-labelling even easier.
- **Changed** Update `open_web_page` tool internal working.

# 1.14.5

- **Fixed** Fix `_ask_for_approval` rejection reason containing `,`

# 1.14.4

- **Fixed** Fix `_ask_for_approval` parameter type so it still works even if `kwargs` contains `ctx`. This fix `analyze_repo` and `analyze_file`.

# 1.14.3

- **Fixed** Kwargs parameter rendering on non yolo confirmation

# 1.14.2

- **Fixed** Yolo mode rendering

# 1.14.1

- **Fixed** Tool confirmation bug

# 1.14.0

- **Feature: YOLO Mode Control in Chat**:
  - Added a `/yolo <true|false>` command to `llm-chat` to dynamically enable or disable YOLO mode (tool execution without confirmation).
  - The initial YOLO mode can be set with the `--yolo` flag when starting `llm-chat` or `llm-ask`.
- **Feature: Granular Internet Access Control for LLM**:
  - Replaced the general `ZRB_LLM_ACCESS_INTERNET` environment variable with more specific controls for internet-accessing tools:
    - `ZRB_LLM_ALLOW_OPEN_WEB_PAGE`
    - `ZRB_LLM_ALLOW_SEARCH_INTERNET`
    - `ZRB_LLM_ALLOW_SEARCH_ARXIV`
    - `ZRB_LLM_ALLOW_SEARCH_WIKIPEDIA`
    - `ZRB_LLM_ALLOW_GET_CURRENT_LOCATION`
    - `ZRB_LLM_ALLOW_GET_CURRENT_WEATHER`
- **Changed: Improved Tool Confirmation Prompt**:
  - The confirmation prompt for running tools now displays the full function call, including arguments, for better user visibility.
  - When rejecting a tool, the user is now required to provide a reason, which is fed back to the LLM.
- **Changed: `write_many_files` Tool Signature**:
  - The `write_many_files` tool now accepts a list of dictionaries (`[{'path': '...', 'content': '...'}]`) instead of a list of tuples, making it more explicit.
- **Changed** The `is_yolo_mode` can now be passed when creating a sub-agent.
- **Fixed** The web runner now no longer inject fake environment variable anymore, it is now correctly use `is_web_mode` parameter while creating a new `SharedContext`, ensuring consistent behavior between web and terminal environments.

# 1.13.3

- **Changed** The `write_many_files` tool now accepts a list of tuples `(file_path, content)` instead of a dictionary. This improves the tool's predictability and consistency.

# 1.13.2

- **Fix** Handle error when toolset is None (which is the default behavior)

# 1.13.0

- **Breaking Change**: Replaced `MCPServer` with `Toolset` for extending LLM capabilities.
  - `LLMTask` now accepts a `toolsets` parameter instead of `mcp_servers`.
  - The methods `add_mcp_server` and `append_mcp_server` have been renamed to `add_toolset` and `append_toolset` respectively.
  - The `create_sub_agent_tool` function now accepts a `toolsets` parameter.
- **Refactor**: Overhauled the LLM context management (`ZRB.md`).
  - The underlying handler has been simplified, removing `LLMContextConfigHandler` and introducing a new markdown parser for better reliability.
  - Context modification is now handled by a single `write_context` method, replacing the previous `add_to_context` and `remove_from_context` methods.
  - Conversation history tools are updated:
    - `add_long_term_info` and `remove_long_term_info` are replaced by `write_long_term_note`.
    - `add_contextual_info` and `remove_contextual_info` are replaced by `write_contextual_note`.
- **Changed**:
  - Updated system and summarization prompts for better clarity and more robust error handling instructions for the AI.
  - Improved the tool confirmation prompt to be more explicit when a tool call is rejected by the user.
- **Dependencies**:
  - Upgraded several key dependencies, including `fastapi`, `pydantic-ai`, and `mistralai`.
- **Fixed**:
  - Added a `try-except` block around `sys.stdin.isatty()` to prevent errors in environments where it's not a standard TTY.

# 0.13.0

- **Breaking changes**: Use `toolset` instead of `mcp_server`
- **Changed**:
  - Fastapi and pydantic-ai mcp servers
  - Simplify ZRB.md management

# 0.12.0

- **Feature: Interactive Mode Switching for LLM Chat**
  - The `llm-chat` command now supports dynamic workflow switching.
  - Use the `/modes` command to view the current modes.
  - Use `/modes <mode1>,<mode2>` to set one or more active modes (e.g., `/modes coding,researching`).
- **Feature: Tool Execution Confirmation (YOLO Mode)**
  - To enhance safety, `zrb` will now prompt for user confirmation before executing any tool suggested by the LLM.
  - This feature can be disabled by setting the environment variable `ZRB_LLM_YOLO_MODE=true`.
- **Changed: Refactored LLM Workflow Configuration**
  - The `llm-ask` task now accepts a `--modes` argument to specify which workflow(s) to use (e.g., `zrb llm-ask --modes coding,copywriting --message "Refactor this code"`).
  - This replaces the previous `ZRB_LLM_MODES` environment variable, which only supported a single mode.
  - The concept of "context enrichment" has been removed, simplifying the conversation management logic.
- **Changed: Renamed Default Workflows**
  - The built-in workflow files have been renamed for clarity:
    - `code.md` -> `coding.md`
    - `content.md` -> `copywriting.md`
    - `research.md` -> `researching.md`
- **Added: New Utility**
  - A new utility `zrb.util.callable.py` has been added to reliably get the name of any callable object, which is used in the new tool confirmation prompt.
- **CI/CD**
  - The `CI_TOOLS` build argument in the `Dockerfile` is now set to `true` by default.

# 1.11.0

- **Changed: Refactored LLM Prompts and Configuration**
  - **Externalized Prompts**: The default prompts (system, interactive, persona, special instructions, summarization) have been moved from hardcoded strings in `src/zrb/config/llm_config.py` to separate `.md` files in `src/zrb/config/default_prompt/`. This makes them easier to manage and customize.
  - **Improved Prompt Loading**: `LLMConfig` now dynamically loads these `.md` files, with a fallback mechanism to use environment variables or instance variables if provided.
  - **Refined Prompt Content**: The prompts themselves have been rewritten to be more explicit, structured, and workflow-oriented. They now include concepts like the "E+V Loop" (Execute and Verify) and a "Debugging Loop".
  - **Better Context Handling**: The logic for handling `@` references to files and directories in user messages has been improved in `src/zrb/task/llm/prompt.py`. It now replaces the reference with a placeholder (e.g., `[Reference 1: file.txt]`) and provides the content in a dedicated "Apendixes" section, which is cleaner.
  - **Robust Markdown Handling**: The `make_prompt_section` utility in `src/zrb/util/llm/prompt.py` is now more robust. It can handle markdown headers within code blocks and automatically adjusts the fence length for code blocks to avoid conflicts. New unit tests have been added for this functionality.
  - **Improved TTY/Web Detection**: The logic for detecting if the CLI is running in an interactive terminal (TTY) or in web mode has been centralized into `SharedContext` (`is_tty`, `is_web_mode`).
- **Feature: Enhanced Testing**
  - **New Test File**: `test/util/llm/test_prompt.py` has been added to test the new prompt utility functions.
  - **Expanded Chat Test Script**: `zrb-test-llm-chat.sh` has been significantly expanded with more comprehensive test cases, including error handling, debugging loops, and safety checks for risky commands.

# 1.10.2

- **Added**
  - Embed time and current directory context to user interaction

# 1.10.1

- **Fixed**
  - Replace references of `ConversationHistoryData` into `ConversationHistory`.

# 1.10.0

- **Changed**
  - Simplify History summarization
  - Remove the following config:
    - `ZRB_LLM_ENRICH_CONTEXT`
    - `ZRB_LLM_CONTEXT_ENRICHMENT_TOKEN_THRESHOLD`
    - `ZRB_LLM_CONTEXT_ENRICHMENT_PROMPT`

# 1.9.17

- **Changed**
  - Improve system prompt

# 1.9.16

- **Changed**
  - Improve system prompt
  - Add software engineering usecase for testing llm_chat

# 1.9.15

- **Fixed**
  - Implement `model_dump_json` for some objects.
  - Increase test coverage.
  - Fix `pluralize` regex

- **Changed**
  - Improve prompt.

# 1.9.13

- **Changed**
  - Minimize dependency to pydantic unless strictly required (i.e., by FastAPI) because it tend to be very slow on termux

# 1.9.12

- **Changed**
  - Remove `ConversationHistory` dependency of pydantic

# 1.9.11

- **Fixed**:
  - Improve load time on git and git_subtree builtin tasks.

# 1.9.10

- **Added**:
  - **LLM Prompt Configuration**:
    - Added `DEFAULT_` constants for LLM system prompts in `config.py`:
      - `_DEFAULT_LLM_ANALYZE_FILE_EXTRACTOR_SYSTEM_PROMPT`
      - `_DEFAULT_LLM_REPO_EXTRACTOR_SYSTEM_PROMPT`
      - `_DEFAULT_LLM_REPO_SUMMARIZER_SYSTEM_PROMPT`
    - Introduced environment variables for overriding these prompts:
      - `ZRB_LLM_ANALYZE_FILE_EXTRACTOR_SYSTEM_PROMPT`
      - `ZRB_LLM_REPO_EXTRACTOR_SYSTEM_PROMPT`
      - `ZRB_LLM_REPO_SUMMARIZER_SYSTEM_PROMPT`

- **Changed**:
  - Code Refactoring: Removed hardcoded system prompts from `code.py` and `file.py`, replacing them with references to `CFG` properties.

# 1.9.8

- **Changed**:
  - Update system prompts

# 1.9.7

- **Changed**:
  - Updated the version in `pyproject.toml` from `1.9.6` to `1.9.7`.
  - Updated default system prompts in `src/zrb/config/llm_config.py` to clarify standing consent for read-only tools.

# 1.9.6

- **Changed**:
  - Replaced `apply_diff` with `replace_in_file` and `write_to_file`. The `apply_diff` function was removed and its functionality is now covered by the more explicit `replace_in_file` and `write_to_file` functions.
- **Fixed**:
  - Incorrect patch targets in `test/task/test_cmd_task.py` and `test/test_main.py`.
  - Update default prompts

# 1.9.5

- **Fixed**:
  - Invalid lazy load because of module name shadowing: `llm_config`, `llm_rate_limitter`

# 1.9.4

- **Changed**:
  - Enhance prompts
  - Changed configuration:
    - Remove: `ZRB_WEB_SUPER_ADMIN_USERNAME` and `ZRB_WEB_SUPER_ADMIN_PASSWORD`
    - Add: `ZRB_WEB_SUPERADMIN_USERNAME` and `ZRB_WEB_SUPERADMIN_PASSWORD`.
  - Make exception catching in context enrichment and summarization more general.

# 1.9.3

- **Changed**:
  - Updated the version in `pyproject.toml` from `1.9.2` to `1.9.3`.
  - Enhanced clarity in the `apply_diff` function's docstring in `src/zrb/builtin/llm/tool/file.py`.
  - Updated default prompts in `src/zrb/llm_config.py` for better workflow and instructions.

# 1.9.2

- **Added**:
  - Added `rich` (`^14.0.0`) as a new dependency for enhanced Markdown rendering in chat sessions.
  - Added support for additional exit commands (`/q`, `/exit`) in the chat session.

- **Changed**:
  - Updated the chat session UI to display `💬 >>` and `🤖 >>` for user and bot prompts, respectively.
  - Simplified and improved the readability of log messages for `UserPromptNode`, `ModelRequestNode`, `CallToolsNode`, and `EndNode`.
  - Updated the display format for tool calls and results to be more concise.
  - Updated the token usage display in `LLMTask` to include an emoji (`💸 Token: {usage}`).

- **Fixed**:
  - Minor dependency updates and improvements.

# 1.9.1

- **Refactored History Management**: The trigger mechanism for history summarization and context enrichment has been changed from being based on the number of conversation turns to the total number of tokens in the history. This provides more accurate, efficient, and cost-effective management of the conversation context.
  - New Configurations: `ZRB_LLM_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD` and `ZRB_LLM_CONTEXT_ENRICHMENT_TOKEN_THRESHOLD` (both default to `3000`).
  - Removed Configurations: `ZRB_LLM_HISTORY_SUMMARIZATION_THRESHOLD` and `ZRB_LLM_CONTEXT_ENRICHMENT_THRESHOLD`.
- **Adjusted Default Rate Limits**: The default LLM API rate limits have been updated to be more conservative and accommodating for free-tier users of various LLM providers.
  - `ZRB_LLM_MAX_REQUESTS_PER_MINUTE` default is now `15` (was `60`).
  - `ZRB_LLM_MAX_TOKENS_PER_MINUTE` default is now `100000` (was `200000`).
  - `ZRB_LLM_MAX_TOKENS_PER_REQUEST` default is now `50000` (was `30000`).

# 1.9.0

- Introduce `zrb.helper.file` and `zrb.helper.task` to simplify `zrb_init.py` scripts.
- Minor bug fixes and performance improvements.

# 1.8.15

- Fixing bug: `\n` automatically trigger mutiline mode on `llm_chat`

# 1.8.14

- Reduce `pydantic` eager load.
- Use `prompt_toolkit` on `llm_chat` and use lazy import to import it.

# 1.8.13

- Introduce interactive prompting, distinguish it from one shot prompting

# 1.8.12

- 💥 Breaking change: Remove `port` from `web_auth_config`
- Revamp docs

# 1.8.11

- Update clipping mechanism

# 1.8.10

- Introduce payload clipping mechanism
- Use token instead of char count

# 1.8.9

- Improve prompts so that the summarization include last conversations in verbatim
- Fix `analyze_file` prompt creation

# 1.8.8

- Rename `SERP_API_KEY` to `SERPAPI_KEY`.
- Improve prompts.

# 1.8.7

- Introduce new configurations: `ZRB_LLM_MAX_REQUESTS_PER_MINUTE`, `ZRB_LLM_MAX_TOKENS_PER_MINUTE`, `ZRB_LLM_MAX_TOKENS_PER_REQUESTS`, and `ZRB_LLM_THROTTLE_SLEEP`.
- Remove old configurations: `LLM_MAX_REQUESTS_PER_MINUTE`, `LLM_MAX_TOKENS_PER_MINUTE`, `LLM_MAX_TOKENS_PER_REQUESTS`, and `LLM_THROTTLE_SLEEP`.

# 1.8.6

- Add `analyze_repo` as `llm_ask` default tool.

# 1.8.5

- Introduce `analyze_repo`
- Introduce `llm_rate_limitter`
- Introduce new configurations: `LLM_MAX_REQUESTS_PER_MINUTE`, `LLM_MAX_TOKENS_PER_MINUTE`, `LLM_MAX_TOKENS_PER_REQUESTS`, and `LLM_THROTTLE_SLEEP`.

# 1.8.4

- Fix typing problem on Coroutine for `BaseTrigger`

# 1.8.3

- Introduce `is_interactive` in `CmdTask`
- Fix buggy output when running CLI with `\r` line endings.

# 1.8.2

- 💥 Breaking change: Remove `ZRB_LLM_CODE_REVIEW_INSTRUCTION_PROMPT`

# 1.8.1

- `read_file` and `analyze_file` is now handling `*.pdf`.
- Update `Dockerfile`, provide `dind` version.

# 1.8.0

- 💥 Breaking change: Rename `web_config` to `web_auth_config`
- Update `pico.css` to `2.1.1`
- Add `ZRB_WEB_FAVICON_PATH`, `ZRB_WEB_JS_PATH`, `ZRB_WEB_CSS_PATH` and `ZRB_WEB_COLOR`
- `fstring_format` is now receiving `{{` and `}}` as escape character

# 1.7.5

- Make `web_config` lazy load.

# 1.7.4

- Include file content while calling `analyze_file`.
- Builtin tools throw errors instead of returning JSON error message.

# 1.7.3

- Make subagent lazy load.
- Add `path` parameter to `analyze_file` tool.

# 1.7.2

- Improve context enrichment mechanism so that it won't override `history_summary`
- Better prompting for `gpt-4o`

# 1.7.1

- Update context enrichment instruction

# 1.7.0

- Fix blocking LLM error.
- Introduce `ZRB_LLM_CODE_REVIEW_INSTRUCTION_PROMPT`.
- Add `analyze_file` tool.

# 1.6.9

- Bug fix: plain logging not added to shared log

# 1.6.8

- Rename `set_default_provider` to `set_default_model_provider` on `LLMConfig`
- Add `default_model` and `default_model_provider` to `LLMConfig`'s contsructor

# 1.6.7

- Add `default_model_settings` config in `llm_config`.

# 1.6.6

- Make version overrideable by using `_ZRB_CUSTOM_VERSION` environment.

# 1.6.5

- 💥 Breaking change: `Cli` constructor no longer has any parameter.

# 1.6.4

- Add `ZRB_ROOT_GROUP_NAME` and `ZRB_ROOT_GROUP_DESCRIPTION`

# 1.6.3

- Patch: Handle cmd output that is not decodable (already a string)

# 1.6.2

- Handle long lines of CmdTask output

# 1.6.1

- Fix LLMTask summarization and context enrichment mechanism

# 1.6.0

- Introduce `ZRB_INIT_FILE_NAME`, `ZRB_BANNER`, `ZRB_WEB_TITLE`, `ZRB_WEB_JARGON`, `ZRB_WEB_HOMEPAGE_INTRO` configuration.
- Change Configuration mechanism, use `zrb.config.CFG` that allows lazy load.
- 💥 Breaking changes:
  - `zrb.builtin.llm.llm_chat` is now `zrb.builtin.llm.llm_ask`
  - We now have `llm_ask` for one time interaction, replacing the old `llm_chat`
  - The new `llm_chat` can only be accessed via CLI

# 1.5.17

- Fix bug on add_git_subtree task, caused by missing parameter

# 1.5.16

- Add new builtin tasks related to JWT, UUID, and HTTP requests
- Add builtin tasks to validate md5 and base64

# 1.5.15

- Fix typing problem in enrich context because of invalid lazy load implementation

# 1.5.14

- Implement lazy load for all pydantic ai and openai dependency

# 1.5.13

- Add note to task execution error for better traceability
- Fix docs

# 1.5.12

- Introduce `append_tool` and `append_mcp_server` to `LLMTask`
- Add `sub_agent`
- Add `context_enrichment_threshold` to `LLMConfig` and `LLMTask`

# 1.5.11

- Add tests

# 1.5.10

- Make LLM prompt shorter
- Fix broken link on zrb base task and the helper on `execute_root` method
- Remove Onnx runtime from poetry.lock

# 1.5.9

- Update Pydantic AI to 0.1.2
- Refactor BaseTask

# 1.5.8

- Refactor LLMTask
- Improve summarization trigger to count part of messages

# 1.5.7

- Add line numbers back

# 1.5.6

- Expand `~` as home directory correctly on LLM tool
- Improve tools
- Introduce summarization + context enhancement on LLMTask

# 1.5.5

- Make LLM tools return JSON

# 1.5.4

- Introduce MCP Server

# 1.5.3

- Add `set_default_persona` to LLM config

# 1.5.2

- Handle tools with empty parameters by adding `dummy` parameter (fix gemini behavior)

# 1.5.1

- Remove dependency to `fastembed`

# 1.5.0

- Remove `read_all_files` as it might use all token
- Roo Code style tools:
  - Rename `read_text_file` to `read_from_file`
  - Rename `write_text_file` to `write_to_file`
  - Introduce `search_files`
  - Introduce `apply_diff`
- Add `filter` parameter on todo tasks

# 1.4.3

- Update tools, use playwright if necessary

# 1.4.2

- Allow modify `default_system_prompt` via `llm_config`

# 1.4.1

- Avoid load file twice (in case of the `zrb_init.py` file in current directory is also existing on `ZRB_INIT_SCRIPTS`)

# 1.4.0

- Introduce LLMConfig
- Rename tool and update signatures:
  - Rename `list_file` to `list_files`
  - Rename `read_source_code` to `read_all_files`
  - Remove parameter `extensions`, add parameters `included_patterns` and `excluded_patterns`.

# 1.3.1

- Fix CRUD filter parsing on UI
- Automatically create migration when adding new column

# 1.3.0

- Introduce `llm_chat.set_default_model`, remove `llm_chat.set_model`
- Introduce `always_prompt` parameter for input

# 1.2.2

- Fix and refactor FastApp CRUD

# 1.2.1

- Fixing Fastapp generator by adding `os.path.abspath`

# 1.2.0

- 💥 When creating any `Input`, use `default` keyword instead of `default_str`.

# 1.1.0

- Fastapp generator is now generating UI when user add new columns (i.e., `zrb project <app-name> create column`)
- Zrb is now loading `zrb_init.py` from parent directories as well, so you can have `zrb_init.py` in your home directory.

# 1.0.0

- 💥 Big rewrite, there are major incaompatibility with version `0.x.x`
