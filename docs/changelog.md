🔖 [Home](../../README.md) > [Documentation](../README.md) > [Changelog](README.md)

## 1.21.37

- **Refactor: Centralized History List Processing**:
  - **New Utility Module**: Introduced `history_list.py` with `remove_system_prompt_and_instruction()` function for consistent history list cleaning across the codebase.
  - **Simplified Agent Runner**: Removed manual instruction pruning logic from `_estimate_request_payload()` in `agent_runner.py`, using the new centralized utility instead.
  - **Enhanced History Processor**: Simplified `history_processor.py` by eliminating redundant instruction filtering and using the unified history list processing approach.
- **Improved: Sub-agent History Management**:
  - **Consistent History Cleaning**: Updated `sub_agent.py` to use the new `remove_system_prompt_and_instruction()` function for cleaner sub-agent conversation history storage.
  - **Reduced Code Duplication**: Eliminated repetitive history processing logic by centralizing system prompt and instruction removal.
- **Enhanced: Main LLM Task Integration**:
  - **Unified History Processing**: Modified `llm_task.py` to leverage the new centralized utility for history list cleaning after agent runs.
  - **Improved Maintainability**: Reduced complexity by replacing inline history processing with dedicated utility function calls.

## 1.21.36

- **Feature: Enhanced CLI Output Display**:
  - **CmdResult Display Property**: Added `display` property to `CmdResult` class for better control over command output presentation.
  - **Improved Output Formatting**: Enhanced CLI tool output with better visual separation and formatting for improved readability.
  - **Rate Limiter Notifications**: Added detailed notifications showing remaining wait time when rate limits (RPM/TPM) are exceeded, providing clearer feedback to users.
- **Performance: History Pruning for LLM Efficiency**:
  - **Optimized Memory Usage**: Implemented history pruning mechanism to reduce context size and improve LLM response times.
  - **Context Leak Prevention**: Fixed potential context leakage issues in LLM sessions for more secure and efficient operation.
- **Framework: Enhanced Tool Integration**:
  - **CmdTask Improvements**: Updated `CmdTask` with better display handling and integration with the new `CmdResult` display property.
  - **RsyncTask Enhancement**: Added support for display property in `RsyncTask` for consistent output formatting.
- **Testing: Comprehensive Test Coverage**:
  - **Rate Limiter Tests**: Added extensive test coverage for LLM rate limiter notifications (`test/config/test_llm_rate_limitter_notification.py`).
  - **CmdTask Validation**: Enhanced `CmdTask` tests to verify proper display property functionality.
  - **Tool Serialization Fix**: Added dedicated test (`test_tool_serialization_fix.py`) to ensure proper tool serialization behavior.
- **Configuration Updates**:
  - **Rate Limiter Configuration**: Enhanced `llm_rate_limitter.py` with improved notification logic and remaining time calculations.
  - **Command Utility Refactoring**: Updated `command.py` with better display handling and output formatting utilities.

## 1.21.34

- **Feature: Enhanced Fuzzy Matching System**:
  - **New Utility Module**: Introduced `fuzzy_match()` function in `src/zrb/util/match.py` with VSCode Ctrl+P style fuzzy search algorithm for better path and option matching.
  - **Chat Completion Integration**: Updated `ChatCompleter` to use fuzzy matching for `@` references, improving file path discovery with smarter token-based scoring.
  - **Option Input Enhancement**: `OptionInput` class now uses fuzzy matching for autocompletion, providing more intuitive option selection in interactive prompts.
- **Feature: Tool Call Preparation Visualization**:
  - **New Configuration**: Added `ZRB_LLM_SHOW_TOOL_CALL_PREPARATION` environment variable (default: `false`) to control display of tool parameter preparation.
  - **Visual Feedback**: When disabled, shows animated "Preparing Tool Parameters..." indicator during tool call preparation for cleaner output.
  - **Improved UX**: Enhanced tool call streaming with better visual separation between parameter preparation and execution phases.
- **Framework: Workflow Discovery Improvements**:
  - **Case-Insensitive Discovery**: Enhanced workflow file detection to support `workflow.md`, `WORKFLOW.md`, and `SKILL.md` filenames for better compatibility.
  - **Expanded Search Paths**: Added support for `.zrb/workflows`, `.zrb/skills`, and `.claude/skills` directories in user home and project locations.
- **Testing: LLM Challenge Suite Updates**:
  - **Improved Setup Instructions**: Updated challenge TASK.md with clearer directory setup commands (`mkdir -p experiment` and proper cleanup).
  - **Enhanced Debugging**: Added `export ZRB_LLM_SHOW_TOOL_CALL_PREPARATION=true` to challenge environment setup for comprehensive tool call visibility.
- **UI Refinements**:
  - **Toolbar Update**: Changed bottom toolbar emoji from 📁 to 📌 for better visual distinction.
  - **Argument Display**: Increased tool argument truncation length from 19 to 30 characters for more informative tool call displays.
- **Bug Fixes**:
  - **Path Completion**: Fixed directory search in chat completer to include directories when searching for `@` references.
  - **Recursive Check**: Improved recursive directory detection logic to handle edge cases with absolute paths.

## 1.21.33

- **Optimization: Enhanced LLM System Prompts**:
  - **Token Efficiency Focus**: Added explicit "Token Efficiency" principle to both interactive and standard system prompts, guiding the LLM to optimize input/output token usage while maintaining quality.
  - **Streamlined Safety Rules**: Consolidated security and safety guidelines into "Safety & Confirmation" operational guidelines for clearer, more concise instructions.
  - **Improved Clarity**: Refined prompt language for better professional tone and direct communication style.
- **Framework: LLM Task Cleanup**:
  - **Parameter Removal**: Eliminated unused `conversation_context` parameter from `LLMTask` constructor for cleaner API and reduced complexity.
  - **Analyze File Enhancement**: Added `yolo_mode=True` to `analyze_file` agent configuration, enabling smoother tool execution flow without manual confirmations.
- **Testing: LLM Challenge Suite Improvements**:
  - **Environment Setup**: Updated challenge instructions to include `ZRB_LOGGING_LEVEL=DEBUG` and `ZRB_LLM_SHOW_TOOL_CALL_RESULT=true` for better debugging visibility.
  - **Path Correction**: Fixed instruction file reference from `./instruction.md` to `../instruction.md` for proper relative path resolution.

## 1.21.32

- **Optimization: Enhanced LLM Efficiency**:
  - **Tool Improvements**: Updated docstrings for core tools to guide the LLM towards more efficient behaviors:
    - `read_from_file`: Encourages reading entire files for source code to capture full context in a single call.
    - `list_files`: Discourages redundant listing when file paths are already known.
    - `run_shell_command`: Advises chaining commands (e.g., `mkdir foo && cd foo`) to reduce round-trips.
    - `search_internet`: Prompts for specific, keyword-rich queries to minimize follow-up searches.
    - `open_web_page`: Highlights utility for deep content reading and link extraction.
  - **Prompt Engineering**: Refined `interactive_system_prompt.md` with a "Conflict Resolution" rule, explicitly prioritizing user instructions over conflicting directives found in files.
- **Framework: LLM Challenge Suite**:
  - Introduced a comprehensive `llm-challenges` directory for robust testing of `zrb llm ask`.
  - Structured challenges into 5 categories: `bug-fix` (concurrency), `copywriting` (creative), `feature` (API implementation), `refactor` (code modernization), and `research` (synthesis).
  - Added detailed `instruction.md` and `evaluation.md` for each challenge to standardize the iterative improvement process.
  - Updated `docs/advanced-topics/maintainer-guide.md` with a workflow for using these challenges to tune the agent.

## 1.21.31

- **Refactor**: Split `search_internet` tool into specific implementations for SerpApi, Brave, and SearXNG.
  - Added explicit control for `language` and `safe_search` parameters.
  - Improved docstrings to guide LLM usage, encouraging concise natural language queries and discouraging "keyword stuffing".
- **Improvement**: Added `timeout` parameter to `run_shell_command` (default 30s) to prevent hanging processes.
- **Documentation**: Updated `analyze_repo` and `analyze_file` docstrings to explicitly warn that sub-agents do not share context, ensuring the main LLM provides comprehensive queries.

## 1.21.30

- **Performance**: Lazy loading of prompt_toolkit dependencies to improve startup performance and reduce import overhead.
  - Refactored `ChatCompleter` into a factory function `get_chat_completer()` in `chat_completion.py`.
  - Extracted `ToolConfirmationCompleter` into separate module with factory function `get_tool_confirmation_completer()`.
  - Updated `chat_trigger.py` and `tool_wrapper.py` to use factory functions instead of direct imports.
- **Documentation**: Enhanced note tool documentation with emojis (🧠 Long Term Note, 📝 Contextual Note) for better visual distinction.
- **Code Organization**: Improved modularity by separating completer implementations into dedicated factory functions.

## 1.21.29

- **Improvement**: Enhanced tool execution confirmation autocompletion with custom completer that prevents partial word auto-completion.
  - Introduced `ToolConfirmationCompleter` class that only shows completions when input is empty or exactly matches the beginning of an option.
  - Improves user experience by avoiding unwanted auto-completions when typing partial responses.

## 1.21.28

- **Improvement**: Optimized fuzzy path search in LLM chat to prevent hanging on broad searches (e.g., `@/`, `@~`).
- **Improvement**: Enhanced LLM chat command autocompletion and slash command support.
- **Improvement**: Better UX for tool execution confirmation (autocomplete for yes/no/edit, optional rejection reason).
- **Refactor**: Updated command descriptions and internal command parsing logic.

# 1.21.27

- **Feature: Enhanced Chat Session Autocompletion**:
  - Introduced a new `ChatCompleter` class in `chat_completion.py` with intelligent command and file path completion.
  - Added fuzzy path search for `@` references with support for both contiguous substring and subsequence matching.
  - Command autocompletion now shows descriptions for all available chat commands (`/help`, `/workflow`, `/attachment`, `/yolo`, `/run`, etc.).
  - Current directory is displayed in the bottom toolbar for better context awareness.
- **Improved: Type System Flexibility**:
  - Updated type definitions in `type.py` to accept both `AnyContext` and `AnySharedContext` in callable attributes.
  - Enhanced `StrAttr`, `BoolAttr`, `IntAttr`, `FloatAttr`, `StrDictAttr`, and `StrListAttr` types for better compatibility across context types.
- **Refactored: Chat Session Command System**:
  - Added descriptive constants for all command descriptions to improve code maintainability.
  - Introduced `_normalize_workflow_str()` function for consistent workflow string handling (removes empty entries, trims whitespace).
  - Updated command display to use command constants instead of hardcoded strings.
- **Enhanced: Option Input Autocompletion**:
  - `OptionInput` class now uses `prompt_toolkit` with `WordCompleter` for TTY environments, providing autocompletion for available options.
  - Improves user experience when selecting from predefined options in interactive prompts.
- **Updated: Attribute Utility Functions**:
  - Modified `get_str_list_attr()`, `get_str_dict_attr()`, `get_str_attr()`, `get_bool_attr()`, `get_int_attr()`, `get_float_attr()`, and `get_attr()` functions in `attr.py` to accept both `AnyContext` and `AnySharedContext`.
  - Ensures consistent attribute retrieval across different context types.

# 1.21.26

- **Improved: Summarization Prompt Strategy**:
  - Implemented a **70/30 split strategy** for history summarization: the oldest 70% of conversation is summarized, while the most recent 30% is preserved as a verbatim transcript.
  - Added specific time format instructions (ISO 8601) to the transcript generation for better temporal context.
  - Introduced strict **anti-looping logic**: tasks listed in `[Completed Actions]` are explicitly excluded from `[Pending Steps]` to prevent the AI from redoing completed work.
  - Added a concrete example in the prompt to guide the model on merging previous summaries with new conversation turns.
- **Documentation: Note Tool Warning Update**:
  - Removed the "Always read first" warning from the `write_long_term_note` and `write_contextual_note` tool docstrings, as it was redundant or potentially misleading in some contexts.

# 1.21.25

- **Enhanced: Sub-agent Configuration Control**:
  - Added `auto_summarize` and `remember_history` parameters to `create_sub_agent_tool()` for fine-grained control over sub-agent behavior.
  - Sub-agents can now be configured to skip automatic history summarization when not needed.
  - History persistence can be disabled for sub-agents that don't require conversation memory.
- **Improved: Token Threshold Management**:
  - Updated default token threshold factors for better resource utilization:
    - History summarization: 0.75 → 0.6
    - Repository analysis extraction/summarization: 0.5 → 0.4
    - File analysis: 0.5 → 0.4
  - Tool call result threshold now dynamically calculated as 40% of max tokens per request.
- **Enhanced: Rate Limiter Notifications**:
  - Added detailed throttle notifications showing whether RPM (requests per minute) or TPM (tokens per minute) limits were exceeded.
  - Notifications now include actual vs. limit counts for better debugging (e.g., "Max request per minute exceeded: 16 of 15").
- **Refactored: Agent Creation Parameters**:
  - Added `auto_summarize` parameter to `create_agent_instance()` to control automatic history summarization.
  - History summarization processor is now conditionally added based on this parameter.
- **Fixed: Parameter Naming Consistency**:
  - Renamed `token_limit` parameter to `token_threshold` in `analyze_file()` function for consistency with other functions.
  - Updated all references to use the new parameter name.

# 1.21.24

- **Improved: History Summarization to Prevent Re-attempts**:
  - Enhanced summarization prompt with clearer instructions to prevent the main LLM from redoing completed work.
  - Added emphasis on using clear, factual language and avoiding verbatim quotes in summaries.
  - Focus summaries on user goals and next actions (open threads or pending steps) rather than completed work.
  - Updated timestamp format in transcript to ISO standard (yyyy-mm-ddTHH:MM:SSZ).
- **Simplified: History Processor Implementation**:
  - Removed markdown formatting functions from history processor for cleaner code.
  - Simplified condensed message format to use JSON directly instead of markdown sections.
  - Cleaned up imports and removed unused dependencies.

# 1.21.23

- **Improved: History Summarization Accuracy**:
  - Enhanced history summarization by removing "instructions" field from all but the latest message in the conversation history.
  - This prevents outdated or conflicting instructions from being included in the summarization process, improving the accuracy and relevance of conversation summaries.
  - The change ensures that only the most recent instructions are considered when creating summaries, while preserving the core content of all messages.

# 1.21.22

- **Enhanced: Sub-agent History Persistence**:
  - Sub-agents now maintain conversation history across invocations, enabling multi-step workflows with memory.
  - Added `agent_name` parameter to `create_sub_agent_tool()` for named history tracking.
  - Introduced `history_processors` parameter to support custom history processing in sub-agents.
  - Sub-agent history is stored in Xcom and persists across the main agent's conversation.
- **Refactored: Agent Architecture**:
  - Extracted `run_agent_iteration()` and related functions into new `agent_runner.py` module for better separation of concerns.
  - `create_agent_instance()` and `get_agent()` now accept `rate_limitter` parameter for fine-grained rate control.
  - Enhanced agent creation with summarization parameters: `summarization_model`, `summarization_model_settings`, `summarization_system_prompt`, `summarization_retries`, `summarization_token_threshold`.
- **Improved: History Summarization Configuration**:
  - Renamed `create_history_processor()` to `create_summarize_history_processor()` for clarity.
  - Summarization now uses default values from `llm_config` when parameters are not provided.
  - Enhanced logging with better indentation and clearer token usage information.
- **New Configuration: Tool Call Result Display**:
  - Added `LLM_SHOW_TOOL_CALL_RESULT` environment variable (default: `false`) to control whether tool call results are displayed.
  - When disabled, tool calls show "Executed" instead of the full result content, reducing output clutter.
- **Enhanced: Xcom Utility Methods**:
  - Added `get()` and `set()` methods to `Xcom` class for simpler value retrieval and assignment.
  - `get()` returns a default value when Xcom is empty, preventing `IndexError`.
  - `set()` pushes a new value and maintains single-item deque behavior.
- **Updated: Conversation History Model**:
  - Added `subagent_history` field to `ConversationHistory` to persist sub-agent conversations.
  - Enhanced serialization/deserialization to handle the new subagent history field.
- **Improved: Sub-agent Tool Integration**:
  - Sub-agents now properly integrate with the main agent's history summarization system.
  - Added `inject_subagent_conversation_history_into_ctx()` and `extract_subagent_conversation_history_from_ctx()` functions for seamless history management.
  - Sub-agent tools can now participate in the conversation history saved to `ZRB.md`.

# 1.21.21

- **Enhanced: Git Branch Pruning**:
  - Added `preserved-branch` input parameter to `prune-local-git-branches` task, allowing users to specify which branches to preserve (default: "master,main,dev,develop").
  - Changed from hardcoded preservation of `main`/`master` to configurable preserved branches for more flexibility.
  - Updated `delete_branch` to use `git branch -d` (safe delete) instead of `-D` (force delete) for safer branch deletion.
- **Improved: LLM History Processing**:
  - Fixed history summarization token estimation to include all message content (no longer strips "instructions" field).
  - Enhanced logging with clearer token usage and threshold information display.
  - Updated agent to use `UsageLimits(request_limit=None)` to avoid artificial request limits during history summarization.
- **Updated: System Prompts**:
  - Refined interactive and standard system prompts for better clarity and professionalism.
  - Changed from "You are an expert interactive AI agent" to "This is an interactive session" for more neutral tone.
  - Changed from "You are an expert AI agent" to "This is a single request session" for consistency.
- **Enhanced: Note Tool Documentation**:
  - Updated `write_long_term_note` and `write_contextual_note` docstrings for better clarity.
  - Changed "USE EAGERLY to save" to "USE EAGERLY to save or update" to emphasize update capability.
- **Fixed: Configuration Variable Names**:
  - Corrected environment variable names in tests (e.g., `ZRB_LLM_FILE_ANALYSIS_TOKEN_LIMIT` → `ZRB_LLM_FILE_ANALYSIS_TOKEN_THRESHOLD`).
- **Dependencies**:
  - Updated `pydantic-ai-slim` from `~1.27.0` to `~1.32.0`.
  - Updated `openai` from `>=2.8.0` to `>=2.11.0`.
  - Updated `pydantic-graph` from `1.27.0` to `1.32.0`.
  - Added new wheel files for `greenlet` and `onnxruntime` packages.

# 1.21.20

- **Refactor: LLM Sub-agent Tool**: The sub-agent tool now returns a raw result instead of a dictionary, simplifying its usage.
- **Fix: LLM Rate Limiter**: Improved error messages in the LLM rate limiter for better debugging.
- **Fix: Repository Analysis**: Adjusted the token threshold for repository analysis to `0.5` to avoid hitting token limits.
- **Refactor: History Processing**: Renamed `history_preprocessor` to `history_processor` and enhanced the history summarization logic for better performance and accuracy.
- **Dependencies**: Updated `poetry.lock` with the latest package versions.

# 1.21.19

- **Refactor: History Summarization**:
  - Overhauled the history summarization mechanism to be a seamless "history processor" injected into the agent execution.
  - Summarization now occurs automatically *before* the main agent processes a request if the token threshold is reached, ensuring context is preserved without interrupting the workflow.
  - Simplified the `ConversationHistory` structure by removing distinct `past_conversation_summary` and `transcript` fields in favor of a unified history list approach.
- **Improved: Dynamic Token Thresholds**:
  - Token thresholds for history summarization and repository analysis now default to a safe percentage (75% or 50%) of the model's maximum context window if not explicitly configured.
  - This prevents hardcoded defaults (like 30k or 75k) from causing errors on models with smaller context windows.
- **Removed: Long Message Warning**:
  - Removed the "Long Message Warning" feature and its associated configurations (`ZRB_LLM_LONG_MESSAGE_WARNING_PROMPT`, `ZRB_LLM_LONG_MESSAGE_TOKEN_THRESHOLD`).
  - The improved automatic summarization renders this manual warning redundant.
- **Dependencies**:
  - Updated `greenlet` and `onnxruntime` dependencies (via `poetry.lock`).

# 1.21.18

- **Feature: Long Message Warning**:
  - Implemented a mechanism to inject a warning message when the conversation history approaches the token limit.
  - Added new configuration options:
    - `ZRB_LLM_LONG_MESSAGE_WARNING_PROMPT`: Sets the warning message.
    - `ZRB_LLM_LONG_MESSAGE_TOKEN_THRESHOLD`: Sets the token threshold to trigger the warning.
- **Improved: LLM Configuration**:
  - Environment variables for LLM rate limiting and token thresholds now accept both singular and plural forms (e.g., `ZRB_LLM_MAX_REQUEST_PER_MINUTE` and `ZRB_LLM_MAX_REQUESTS_PER_MINUTE`).
  - Renamed `ZRB_LLM_FILE_ANALYSIS_TOKEN_LIMIT` to `ZRB_LLM_FILE_ANALYSIS_TOKEN_THRESHOLD` for consistency.
- **Refactor: History Processing**:
  - Introduced `history_processors` to the LLM agent, allowing for more flexible modification of the conversation history.
  - The long message warning is implemented as a history processor.
  - Removed the `replace_system_prompt_in_history` function in favor of the new history processor system.
- **Refactor**: Renamed `LLMRateLimiter` to `LLMRateLimitter` for consistency.
- **Docs**: Added code block examples to docstrings for `read_from_file`, `write_to_file`, and `replace_in_file` tools.

# 1.21.17

- **Updated Dependency**: Update Pydantic AI to 1.27.0

# 1.21.16

- **Enhanced: Note Tool Documentation**: Improved documentation for long-term and contextual note tools:
  - Added "User information (e.g., user name, user email address)" and "Anything that will be useful for future interaction across projects" to `write_long_term_note` usage guidelines
  - Updated `write_contextual_note` with clearer terminology: "Architectural patterns for this project/directory" and "Anything related to this directory that will be useful for future interaction"
- **Improved: Workflow Prompt Formatting**: Enhanced workflow display in prompts with better formatting:
  - Added "Workflow status: Automatically Loaded/Activated" indicator
  - Improved workflow location display with backticks for better readability

# 1.21.15

- **Enhanced: Interactive File Replacement Editor**: Major refactoring of `edit_replacement()` function with improved user experience:
  - Added `difflib` integration for smarter diff generation
  - Implemented optimized replacement generation based on user edits
  - Added context expansion and word boundary detection for better replacement accuracy
  - New helper functions: `_apply_initial_replacements()`, `_open_diff_editor()`, `_generate_optimized_replacements()`, `_group_opcodes_into_hunks()`, `_create_replacement_from_hunk()`, `_expand_context_for_uniqueness()`, `_expand_to_word_boundary()`
- **Enhanced: Diff Editor Support**: Expanded `_get_default_diff_edit_command()` with support for more editors:
  - Added support for code, vscode, vscodium, windsurf, cursor, zed, zeditor, agy, emacs
  - Enhanced vim/nvim configuration with syntax highlighting and on-screen instructions
  - Improved editor integration with better command templates
- **Configuration: Rate Limiting Improvements**:
  - Changed default `LLM_THROTTLE_SLEEP` from 1.0 to 5.0 seconds for better rate limit compliance
  - Added `_limit_token_threshold()` method to automatically limit token thresholds based on rate limits
  - Updated token threshold configurations (`LLM_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD`, `LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD`, `LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD`, `LLM_FILE_ANALYSIS_TOKEN_LIMIT`) to use new limiting method
- **Improved: Error Messages**: Enhanced LLM rate limiter error messages to show actual token counts for better debugging
- **Dependencies**: Updated poetry.lock with new wheel files for greenlet and onnxruntime

# 1.21.14

- **Fix** When there are multiple replacements and user type `edit` without actually change the content, the new replacement only contains the last replacement.

# 1.21.13

- **Feature: Interactive File Replacement Editor**: Introduced new `edit_replacement()` function that allows users to interactively edit file replacements using diff tools (nvim, code, hx, vimdiff)
- **Feature: Enhanced Note Tool Documentation**: Completely revamped note tool prompts with clearer guidance on when to use long-term vs contextual notes and warnings about overwriting
- **Refactored: File Tool Architecture**: Extracted `FileToRead`, `FileToWrite`, and `FileReplacement` TypedDict definitions into separate `file_tool_model.py` module for better maintainability
- **Configuration: Diff Editor Support**: Added `DEFAULT_DIFF_EDIT_COMMAND_TPL` configuration with support for multiple editors and customizable diff commands
- **Improved: File Replacement Validation**: Added `is_single_path_replacement()` checker function to validate replacement operations
- **Enhanced: Tool Wrapper Integration**: Updated tool wrapper to support interactive editing of file replacement parameters
- **Documentation: Read From File Metadata**: Enhanced `read_from_file` documentation to clarify line number formatting in returned content
- **Optimization: Dependency Cleanup**: Removed unnecessary platform-specific wheel files from poetry.lock

# 1.21.12

- **Updated dependencies**: `mcp` `1.22.0` → `1.23.1`
- **Fixed typing**: Improved type annotations for `StrAttr`, `BoolAttr`, `IntAttr`, `FloatAttr` to accept `None` return values from callables
- **Refactored**: Updated `read_chat_conversation` and `write_chat_conversation` functions to use `AnyContext` instead of `AnySharedContext` for better type consistency
- **Improved documentation**: Enhanced `write_to_file` docstring for better clarity on append mode usage
- **Enhanced workflow prompts**: Updated coding workflow description and prompt construction logic
- **Improved YAML editing**: Added `width=float("inf")` parameter to `yaml_dump` function for better formatting
- **Fixed text editing**: Enhanced `edit_text` function to properly handle empty prompt messages
- **Enhanced LLM task configuration**: Updated type annotations for `model_base_url`, `model_api_key`, `persona`, `system_prompt`, `special_instruction_prompt`, and `yolo_mode` parameters

# 1.21.11

- **Improved**: Update tool docstring for `write_to_file` and `replace_in_file` ensuring no double escape character.

# 1.21.10

- **Updated dependencies**: `pydantic-ai-slim` `~1.25.1`

# 1.21.9

- **Refactor**: Major improvement to `replace_in_file` tool:
  - Simplified API: Removed nested `replacement` structure, now uses flat `old_text` and `new_text` parameters
  - Added `count` parameter to control how many occurrences to replace (default: -1 for all)
  - Improved performance by grouping replacements by file path to minimize I/O operations
  - Enhanced documentation with clearer examples and usage patterns
  - Updated all tests to reflect the new API

# 1.21.8

- **Improved**: Make `replace_in_file` documentation more clear.

# 1.21.7

- **Changed**: `list_files` tool has been simplified and improved.
  - Removed `recursive` parameter.
  - Added `depth` parameter (default: 3).
  - `depth=0` lists immediate children (files and folders), similar to `ls`.
  - `depth > 0` lists files recursively up to the specified depth.
  - Negative depth values are clamped to 1.

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
