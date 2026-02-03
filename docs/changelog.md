🔗 [Home](../../README.md) > [Documentation](../README.md) > [Changelog](README.md)

## 2.0.18

- **Feature: Sub-Agent Detection & Delegation**:
  - **Enhanced Delegation**: Implemented a robust `delegate_to_agent` tool and logic in `AgentManager` to improve how the main agent hands off tasks to specialized sub-agents.
  - **Smart Detection**: improved logic to detect when a sub-agent should be invoked based on task complexity or specificity.
- **Refactor: Agent & Prompt Organization**:
  - **Plugin-Based Agents**: Moved built-in agent definitions (Coder, Planner, Researcher, Reviewer) from general prompt directories to a dedicated `src/zrb/llm_plugin/agents/` structure, treating them more like plugins.
  - **Prompt Manager Updates**: Refactored `PromptManager` to align with the new agent plugin structure.
- **Refinement: Core Prompts & Mandates**:
  - **Strict Verification**: Updated `mandate.md` to explicitly require checks for keywords, structure, and citations in text and research tasks.
  - **Loop Prevention**: Added explicit loop prevention and stop condition directives to the `Coder` agent to reduce redundant tool calls.
  - **Planning Rigor**: Updated the `Planner` agent to explicitly list required artifacts, keywords, and format constraints during the requirements phase.
  - **Research Standards**: Mandated the inclusion of a "References" section for the `Researcher` agent.
- **Improvement: LLM Challenges**:
  - **Updated Benchmarks**: Refreshed runner scripts and experiment results to reflect the improved agent behaviors.

## 2.0.17

- **Feature: Enhanced Prompt Management & Active Skills**:
  - **Active Skills Support**: Added `active_skills` parameter to `PromptManager` and `create_claude_skills_prompt` to allow pre-loading skill content directly into system prompts.
  - **Project Context Separation**: Split `create_claude_skills_prompt` into two functions: `create_claude_skills_prompt` (skill management) and `create_project_context_prompt` (CLAUDE.md/AGENTS.md loading).
  - **Configurable Project Context**: Added `include_project_context` parameter to `PromptManager` to control whether project documentation is included.
- **Improvement: Tool Safety Wrapper Centralization**:
  - **Moved Safety Logic**: Consolidated tool error handling from `LLMTask` into `create_agent` function in `common.py` for consistent safety across all agent usage.
  - **Robust Error Handling**: Tools and toolsets are now automatically wrapped with error handling to prevent agent crashes from faulty tool calls.
- **Refinement: Core Prompts & Code Quality**:
  - **Updated Mandate**: Refined communication protocol in `mandate.md` for clearer guidance on when to be concise vs. provide detailed explanations.
  - **Import Cleanup**: Streamlined import statements in `llm_chat_task.py` and `llm_task.py` for better code organization.
  - **Type Hint Improvements**: Enhanced type annotations throughout the prompt management system.

## 2.0.16

- **Fix: Fix Zrb skill directory path**: The Zrb skill directory path is now `~/.zrb/skills`

## 2.0.15

- **Fix: LLM Configuration & Task Handling**:
  - **Empty Model Name Handling**: Fixed an issue in `LLMChatTask` and `LLMTask` where empty string model names were not correctly treated as `None`, potentially causing model resolution failures.
- **Feature: LLM Chat Enhancements**:
  - **Model Input Support**: The built-in `llm_chat` task now accepts a `model` input argument, allowing for dynamic model selection during task execution.
- **Refinement: Runner & Documentation**:
  - **Model Naming Convention**: Updated `llm-challenges` runner script and documentation to support and encourage specific model naming (e.g., `google-gla:gemini-2.5-flash`) for better clarity and compatibility.
  - **Updated Dependencies**: Bumped version to `2.0.15`.

## 2.0.14

- **Fix: LLM Configuration & Custom Provider Support**:
  - **Model Resolution**: Fixed a bug where custom `Model` objects (e.g., for DeepSeek or OpenAI-compatible proxies) were being stringified when passed to sub-tasks, causing "Unknown model" errors.
  - **Provider Intelligence**: Enhanced `LLMConfig` to intelligently resolve providers based on model names, ensuring custom `base_url` and `api_key` are correctly applied to OpenAI-compatible models while maintaining compatibility with native providers like Anthropic and Google.
- **Fix: Robustness & Stability**:
  - **Serialization Safety**: Implemented input sanitization in `Session.as_state_log()` to prevent `PydanticSerializationError` when task inputs contain non-serializable objects (like LLM clients or models).
  - **CLI Entry Point**: Added a proper `if __name__ == "__main__":` block to `src/zrb/__main__.py` to ensure the CLI executes correctly when run as a module via `python -m zrb`.

## 2.0.13

- **Feature: Dynamic YOLO & Model Switching**:
  - **Runtime YOLO Toggle**: Added ability to toggle "YOLO mode" (skipping tool approval) dynamically while the agent is running using `/yolo` or `Ctrl+Y`.
  - **Model Switching**: Introduced `/model <name>` command to switch LLM models on the fly.
  - **Enhanced Autocompletion**: Implemented VS Code-style fuzzy completion for commands and model names, including a programmatically generated list of supported models from `pydantic-ai`.
- **Improvement: Robustness & Safety**:
  - **Safe Toolset Execution**: Wrapped `AbstractToolset` execution to catch and report errors gracefully to the LLM, preventing agent crashes from faulty tool calls.
  - **Expanded Skill Discovery**: Updated `SkillManager` to look for skills in `.zrb/skill` (or configured root group name) in addition to the standard `.claude/skills` directory.
- **Refinement: Core Logic**:
  - **Prompt Manager**: Enhanced `PromptManager` to accept raw strings as prompts, automatically wrapping them with context rendering logic.
  - **XCom Usage**: Refined `LLMChatTask` and `UI` to use `Xcom` objects for shared state management (YOLO mode), ensuring proper synchronization.
  - **Prompt Accuracy**: Merged improvements for better prompt accuracy and challenge handling.

## 2.0.12

- **Feature: LLM Challenge Suite**: Added a comprehensive suite of challenges in `llm-challenges/` for benchmarking AI agent performance in scenarios like bug fixing, refactoring, and copywriting.
- **Refinement: Core Prompts**:
  - **Updated Mandate & Persona**: Refined `mandate.md` and `persona.md` to ensure better alignment with the agent's operating directives and persona.
  - **Renamed Compatibility Module**: Renamed `claude_compatibility.py` to `claude.py` for better clarity.
- **Documentation**:
  - **Updated Agent Guide**: Comprehensive update to `AGENTS.md` to provide clearer context and guidelines for LLMs working with the Zrb project.
- **Remove CI_TOOLS argument from Dockerfile**

## 2.0.11

- **Fix: Exclude `.claude` directory from code analysis**

## 2.0.10

- **Feature: Structured History Summarization**:
  - **XML State Snapshot**: Overhauled the summarizer prompt to generate structured `<state_snapshot>` XML (Goals, Constraints, Knowledge, Artifacts, Tasks) instead of unstructured text, improving the agent's long-term memory and context retention.
  - **Iterative Chunking**: Implemented smart history splitting to process large conversations in manageable chunks, preventing context window overflows.
  - **Recursive Compression**: Added logic to recursively re-summarize content if the aggregated summary remains too large.
- **Improvement: Rate Limiting & Safety**:
  - **Token-Aware Truncation**: Added `truncate_text` to `LLMLimiter` with `tiktoken` support (and fallback) to safely handle massive message blocks during summarization.
  - **Prompt Injection Defense**: Added explicit security rules to the summarizer system prompt to ignore adversarial content within the chat history.
- **Refinement: Core Prompts**:
  - **Mandate & Persona**: Polished `mandate.md` and `persona.md` for better clarity and stricter adherence to safety and convention guidelines.
- **Maintenance**:
  - Updated dependencies (`poetry.lock`, `pyproject.toml`).

## 2.0.9

- **Fix: CFG.LLM_ASSISTANT_NAME lazy load**

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