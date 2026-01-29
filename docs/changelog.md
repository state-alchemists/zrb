🔗 [Home](../../README.md) > [Documentation](../README.md) > [Changelog](README.md)

## 2.0.8

- **Fix: Art resolution** Fixing art resolution in case of user provided the file

## 2.0.7

- **Update: ASCII Art Collection**:
  - Added new ASCII art files: `batman.txt`, `butterfly.txt`, `clover.txt`, `hello-kitty.txt`, and `star.txt` under `src/zrb/util/ascii_art/art/`.
  - Updated banner ASCII art format in `src/zrb/util/ascii_art/banner.py`.
  
- **Enhancement: LLM Prompt Management**:
  - Added new markdown-based prompts for various roles such as `executor`, `orchestrator`, `planner`, `researcher`, and `reviewer` under `src/zrb/llm/prompt/markdown/`.

- **Improvement: LLM Configuration**:
  - Reviewed and possibly updated configurations related to LLM management in `src/zrb/config/config.py`.
  - The default configuration for web components and token thresholds is now more flexible.
  
- **Minor Fixes & Adjustments**:
  - Increased readability of the `Config` class with comprehensive property management.
  - `src/zrb/builtin/llm/chat.py` adapted to improve task and tool management for LLM operations.

## 2.0.6

- **Feature: Hierarchical Prompt Configuration**:
  - **Recursive Prompt Discovery**: Updated `get_default_prompt` to traverse up the directory tree (up to the home directory) when searching for custom prompt overrides.
  - **Improved Search Logic**: Implemented `_get_default_prompt_search_path` to intelligently identify search paths only when the current directory is within the home directory.
- **Improvement: LLM History Management**:
  - **Lazy Initialization Fix**: Refactored `LLMTask` and `LLMChatTask` to ensure `FileHistoryManager` is properly initialized before use, preventing potential `AttributeError`.
- **Bug Fixes & Refinements**:
  - **Fixed Test Integration**: Updated `test_tool_policy_integration.py` to ensure `test_print` accepts arbitrary keyword arguments, maintaining compatibility with internal streaming response utilities.
- **Testing**:
  - **New Prompt Traversal Tests**: Added comprehensive unit tests in `test/llm/prompt/test_default_prompt.py` to validate hierarchical prompt discovery.
  - **Updated Task Tests**: Enhanced `test/llm/task/test_llm_task_tool_confirmation.py` with mock history managers to ensure stability.

## 2.0.5

- **Feature: Enhanced Context Management**:
  - **Global ContextVar System**: Introduced `current_ctx` ContextVar and `zrb_print()` function for consistent, context-aware printing throughout the codebase.
  - **Task Execution Context**: Added proper context management to task execution, ensuring context variables are properly set and reset during task runs.
  - **Tool Factory Support**: Added `tool_factories` and `toolset_factories` parameters to `LLMChatTask`, enabling dynamic tool resolution based on runtime context.
- **Improvement: Configuration Consistency**:
  - **Standardized Config Property Names**: Updated `LLM_MAX_REQUESTS_PER_MINUTE` to `LLM_MAX_REQUEST_PER_MINUTE` (singular) for consistency with other config properties.
  - **Backward Compatibility**: Maintained support for old environment variable names (`LLM_MAX_REQUESTS_PER_MINUTE`) while preferring the new singular form.
- **Improvement: Rate Limiting & Token Management**:
  - **Enhanced Token Counting**: Improved token estimation with better fallback approximation (char/3 instead of char/4) and 95% buffer for context window management.
  - **Better Rate Limit Notifications**: Added cyan styling to rate limit messages and improved notification clearing mechanism.
  - **Smarter Throttling**: Enhanced `_can_proceed()` logic to handle empty logs more gracefully.
- **Improvement: UI/UX Enhancements**:
  - **Consistent Styling**: Applied `stylize_faint()` and `stylize_error()` to UI messages for better visual hierarchy.
  - **Improved Command Display**: Streamlined command output formatting with timestamps inline.
  - **Better Error Feedback**: Enhanced error messages with proper styling throughout the TUI.
- **Improvement: History & Conversation Management**:
  - **Summarization Feedback**: Added progress notifications when compressing conversations due to token threshold limits.
  - **Consistent Printing**: Updated `FileHistoryManager` to use `zrb_print()` for consistent error/warning messages.
- **Bug Fixes & Refinements**:
  - **Fixed Tool Name Assignment**: Removed explicit `__name__` assignment from note tools as pydantic-ai handles this automatically.
  - **Improved Tool Resolution**: Enhanced `LLMChatTask` to properly resolve tools from factories during execution.
  - **Better Async Context Management**: Added proper async context stack management for toolsets with `__aenter__` support.
  - **Fixed Test Compatibility**: Updated tests to pass context to `_create_llm_task_core()` method.
- **Code Quality**:
  - **Consistent Printing**: Replaced direct `print()` calls with `zrb_print()` throughout LLM tools (bash, code, mcp, rag, note).
  - **Prompt Manager Reset**: Added `reset()` method to `PromptManager` for easier testing and reinitialization.
  - **Type Safety**: Cleaned up imports and type annotations in agent common module.

## 2.0.3

- **Feature: Context-Aware LLM Agent Execution**:
  - **UI & Tool Confirmation Inheritance**: Introduced `ContextVar`-based context management for UI and tool confirmation settings, allowing sub-agents to automatically inherit parent agent configurations.
  - **Improved Event Handling**: Enhanced streaming response management with better UI integration and configurable event handlers.
  - **Enhanced Rate Limiting**: Updated rate limiter to accept message/history context for more accurate token estimation and throttling.
- **Improvement: Skill Command System**:
  - **Fixed Skill Command Factory**: Resolved function signature issue by removing unnecessary splat operator and implementing proper factory pattern for dynamic skill command loading.
  - **Enhanced Custom Command Resolution**: Improved LLM chat task to support both direct commands and factory functions for custom command registration.
- **Improvement: History Summarization**:
  - **Better Message Representation**: Added `message_to_text()` function to convert pydantic_ai messages into readable text for more accurate history summarization.
  - **Default Summarizer**: LLM chat tasks now automatically include a summarizer history processor by default to manage long conversation histories.
- **Bug Fixes & Refinements**:
  - **Fixed Faint Printer**: Corrected `create_faint_printer()` to accept a print function instead of context, resolving compatibility issues with streaming responses.
  - **Improved Argument Extraction**: Fixed typo in `_extract_args()` function parameter name for consistency.
  - **Enhanced Sub-Agent Tool**: Updated sub-agent tool to leverage automatic UI and tool confirmation inheritance via context variables.
- **Code Quality**:
  - **Clean Architecture**: Improved separation of concerns in agent execution with proper context management and cleanup.
  - **Type Safety**: Enhanced type annotations and error handling throughout the LLM module.

## 2.0.2

- **Improvement: Enhanced Skill Management**:
  - **Depth-Controlled Scanning**: Added `max_depth` parameter to `SkillManager` to control recursive directory scanning depth, improving performance for large projects.
  - **Customizable Ignore Patterns**: Introduced `ignore_dirs` parameter allowing users to customize which directories to skip during skill discovery.
  - **Refined Directory Ignore List**: Updated default ignore patterns to be more focused on build artifacts and less on IDE-specific directories.
  - **Improved Error Handling**: Added robust try-catch blocks to gracefully handle permission errors and inaccessible directories during skill scanning.
- **Code Quality & Maintenance**:
  - **Cleanup**: Removed unused import (`ToolCallHandler`) from `llm_chat_task.py` to reduce code clutter.
  - **Naming Consistency**: Refactored `IGNORE_DIRS` constant to `_IGNORE_DIRS` following Python convention for module-private variables.
- **Testing**:
  - **Comprehensive Depth Testing**: Added thorough unit tests for the new `max_depth` functionality, ensuring skill discovery respects depth limits.
  - **Edge Case Coverage**: Enhanced test suite to validate skill manager behavior with deeply nested directory structures.

## 2.0.1

- **Feature: Enhanced LLM Interaction**:
  - **Slash Commands for Skills**: Automatically converted user-invocable Claude skills into executable slash commands (e.g., `/<skill-name>`) within the chat TUI.
  - **Dynamic Argument Extraction**: Implemented automatic argument detection and parsing for skill-based slash commands.
  - **Safer Tool Policies**: Improved `auto_approve` tool policy with directory-aware checks, automatically approving read operations only within the current working directory.
- **Improvement: LLM Prompt & Mandate**:
  - **Assertive Mandate**: Updated the core mandate to be more assertive, explicitly requiring the AI to check the provided system context before using discovery tools.
  - **Streamlined System Context**: Flattened the system context structure to remove redundant headers and improve token efficiency.
  - **Anti-Hallucination Measures**: Added explicit instructions to prevent the AI from defaulting to "You are absolutely right" and instead focus on reasoned explanations.
- **Documentation**:
  - **New Guide**: Added [Customizing the AI Assistant](./advanced-topics/customizing-ai-assistant.md) guide.
  - **Updated Docs**: Comprehensive updates to task type documentation, configuration guides, and architectural overviews to match the 2.0 architecture.
- **Bug Fixes & Refinement**:
  - Fixed argument residue handling in custom chat commands.
  - Improved autocompletion metadata for custom commands in the TUI.
  - Refined skill management to distinguish between model-invocable and user-invocable skills.

## 2.0.0

- **Refactor: Major Architectural Overhaul**:
  - **LLM Module Consolidation**: Moved all LLM-related logic from `src/zrb/builtin/llm` and `src/zrb/task/llm` to a unified `src/zrb/llm` package for better modularity and maintainability.
  - **Tool Relocation**: LLM tools (e.g., `analyze_repo`, `write_to_file`) are now located in `zrb.llm.tool`.
  - **Centralized Configuration**: Merged multiple LLM-specific and project-wide configuration files into a robust, centralized `Config` class in `src/zrb/config/config.py`.
- **Feature: Enhanced LLM Interface**:
  - **Interactive TUI**: Introduced a new, feature-rich Terminal User Interface (TUI) for `llm-chat`, providing a more responsive and visually appealing experience with syntax highlighting and custom layouts.
  - **Improved Command Structure**: Consolidated and refined LLM-related commands (e.g., `/save`, `/load`, `/attach`, `/exec`) for better usability.
  - **ASCII Art & Banners**: Added customizable ASCII art and banners for the CLI and AI assistant.
- **Feature: Prompt & Agent Management**:
  - **Centralized Prompt System**: Introduced a more robust prompt management system with support for markdown-based templates.
  - **Skill Management**: Introduced a new skill management system to extend LLM capabilities dynamically via `SkillManager`.
  - **New Agent Framework**: Re-implemented LLM agents with better history tracking, summarization, and tool-call policies.
- **Feature: LLM Challenge Suite**:
  - **Benchmarking**: Added a comprehensive suite of challenges in `llm-challenges/` for benchmarking AI agent performance in scenarios like bug fixing, refactoring, and copywriting.
- **Performance & Cleanup**:
  - **Code Pruning**: Conducted a significant "prune" of the codebase, removing redundant components, old tests, and unused dependencies to improve startup time and reduce package size.
  - **Lazy Loading**: Further optimized imports to ensure faster CLI responsiveness.
- **Testing**:
  - **Updated Test Suite**: Completely refactored the test suite to align with the new architecture, ensuring high coverage and stability for the 2.0 release.

  [Changelog v1](./changelog-v1.md)