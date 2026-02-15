🔗 [Home](../../README.md) > [Documentation](../README.md) > [Changelog](README.md)

## 2.3.2

- **Feature: Enhanced LLM Challenge Framework**:
  - **New Integration-Bug Challenge**: Added comprehensive "integration-bug" challenge type with banking system scenario to test agent ability to identify and fix integration issues between multiple components.
  - **Modular Feature Challenge Architecture**: Refactored feature challenge from monolithic `todo_app.py` to proper FastAPI application structure (`app/database.py`, `app/models.py`, `app/main.py`) for more realistic development testing.
  - **Standardized Verification Scripts**: Updated all challenge verification scripts for consistency and improved error handling across bug-fix, feature, refactor, and research challenge types.

- **Improvement: Specialized Agent System**:
  - **Coder Agent Redefinition**: Transformed coder agent into "Senior Staff Engineer and Brownfield Expert" with focus on safe legacy integration and zero-regression modifications.
  - **New Explorer Agent**: Added discovery specialist for rapid, read-only mapping of unfamiliar codebases and system structures.
  - **New Generalist Agent**: Created polymath executor capable of direct action across all domains for complex multi-step tasks.
  - **Enhanced Planner, Researcher & Reviewer Agents**: Updated directives and tooling for improved architectural planning, evidence-based research, and rigorous code review.

- **Improvement: LLM Evaluation & Benchmarking**:
  - **Expanded Experiment Results**: Updated comprehensive evaluation across 10+ LLM providers (DeepSeek, Google Gemini variants, OpenAI GPT variants, Ollama models) with latest performance metrics.
  - **Enhanced Reporting**: Updated `REPORT.md` with detailed timing, tool usage, and success rates for all challenge types including new integration-bug category.
  - **Baseline Experiment Directories**: Added standardized experiment directories for bug-fix, feature, refactor, and research challenges to facilitate consistent benchmarking.

- **Improvement: Core Prompt Refinements**:
  - **Updated Mandate & Persona**: Refined `mandate.md` and `persona.md` with clearer operational directives and improved agent behavior guidelines.
  - **Structured Agent Definitions**: Enhanced agent markdown files with more specific tool sets, operational mandates, and specialized personas.

## 2.3.1

- **Improvement: Assertive Operational Mandates**:
  - **Imperative Prompting**: Rebuilt core persona (`persona.md`) and mandate (`mandate.md`) using strict **MUST ALWAYS** and **NEVER** directives, transitioning from descriptive guidance to non-negotiable engineering mandates.
  - **Tool Selection Hierarchy**: Mandated a strict discovery hierarchy (`Read` > `Glob` > `LS`) to eliminate redundant token consumption and prevent "blind exploration" when paths are already known.
  - **Verification Loop**: Upgraded implementation steps into a mandatory **Plan -> Act -> Validate** cycle, forbidding assumed success without test/linter verification.

- **Feature: "High-Signal" Memory Management**:
  - **Atomic Note Mandate**: Strictly instructed the agent to save only small, high-signal, and rarely-changing architectural facts or user preferences to `WriteContextualNote` and `WriteLongTermNote`.
  - **Read-before-Write Workflow**: Mandated checking existing notes before updates to prevent context loss or redundant duplication.
  - **Context Restoration**: Improved state snapshots to prioritize evidence-backed insights over raw history preservation.

- **Improvement: Technical Tool Optimization**:
  - **Enhanced AnalyzeCode**: Added `include_patterns` parameter for granular search control and mandated the use of `extensions` and glob patterns to limit search space.
  - **Refined Search Tools**: Updated `search_files` (Grep) and `analyze_file` docstrings with strict efficiency mandates and usage warnings.
  - **Research Rigor**: Enforced an "OpenWebPage Mandate" for research tasks, requiring full content verification of all search snippets and mandatory citation of verified sources.

- **Improvement: TUI & UX Refinement**:
  - **Focus & Navigation**: Added F6 key to toggle focus between input and output fields and removed redundant TAB navigation hints.
  - **Smooth Scrolling**: Implemented smarter scrolling logic that keeps the latest content in view when the input field is focused or when already at the bottom of the buffer.
  - **Refresh Stability**: Increased UI refresh rate to `0.1s` for smoother streaming and reduced visual artifacts during reasoning.

## 2.3.0

- **Refactor: Tool Registry Removal & Explicit Tool Registration**:
  - **Tool Registry Removal**: Eliminated the centralized `ToolRegistry` class (`src/zrb/llm/tool/registry.py`) in favor of explicit, direct tool registration for better clarity and control.
  - **Explicit Tool Registration**: Tools are now explicitly added to both `LLMChatTask` and `SubAgentManager` instead of being loaded from a registry, improving transparency and reducing indirection.
  - **Enhanced Agent Manager**: Updated `SubAgentManager` to support explicit tool and tool factory registration, enabling better control over tool availability for sub-agents.
  - **Tool Factory Support**: Added comprehensive support for tool factories in both `LLMChatTask` and `SubAgentManager`, allowing dynamic tool resolution based on runtime context.

- **Improvement: Modular Note Tool Architecture**:
  - **Separate Tool Factories**: Refactored note tools into individual factory functions (`create_read_long_term_note_tool`, `create_write_long_term_note_tool`, `create_read_contextual_note_tool`, `create_write_contextual_note_tool`) for better modularity and testability.
  - **Proper Tool Naming**: Each note tool now explicitly sets its `__name__` attribute to ensure consistent tool identification in the LLM interface.
  - **Comprehensive Testing**: Added new test suite (`test/llm/tool/test_note.py`) with thorough coverage for all note tool operations including long-term and contextual note reading/writing.

- **Feature: Enhanced Tool Safety Policies**:
  - **Path-Based Approval**: Introduced `approve_if_path_inside_cwd` tool policy function that automatically approves file operations only when target paths are within the current working directory, improving security for file system interactions.
  - **Chat Tool Policy Integration**: Added new `chat_tool_policy.py` module with robust path validation logic to prevent unauthorized file access.

- **Improvement: LLM Chat Configuration**:
  - **Simplified Tool Loading**: Streamlined tool initialization in `llm_chat` task by removing registry-based loading and implementing direct tool registration.
  - **Consistent Tool Availability**: Ensured all tools are available to both main chat agent and sub-agents through synchronized registration to both `LLMChatTask` and `SubAgentManager`.
  - **Removed Redundant Tests**: Cleaned up test suite by removing `test_registry_extended.py` which tested the now-removed registry functionality.

- **Maintenance: Dependency Updates**:
  - **Version Bump**: Updated to version 2.3.0 in `pyproject.toml`.
  - **Lock File Refresh**: Updated `poetry.lock` with latest dependency resolutions.

## 2.2.15

- **Feature: Tool Call Validation Policies**:
  - **Read File Validation**: Added `read_file_validation_policy` to automatically reject `Read` tool calls if the target file does not exist, providing immediate feedback to the agent.
  - **Read Many Files Validation**: Added `read_files_validation_policy` to reject `ReadMany` tool calls if none of the specified files are found on the system.
  - **Edit Validation**: Added `replace_in_file_validation_policy` that proactively rejects `Edit` tool calls if:
    - `old_text` and `new_text` are identical.
    - The target file does not exist.
    - The `old_text` to be replaced is not found in the file content.

- **Improvement: LLM Chat Reliability**:
  - **Integrated Validation**: Automatically applied the new validation policies to the built-in `llm_chat` task, reducing failed tool executions and improving agent recovery.

- **Refactor: Tool Call Component Organization**:
  - **Standardized Naming**: Renamed tool call components for better clarity and consistency:
    - `replace_in_file.py` → `replace_in_file_formatter.py` (Argument Formatter)
    - `write_file.py` → `write_file_formatter.py` (Argument Formatter)
    - `replace_in_file.py` → `replace_in_file_response_handler.py` (Response Handler)

- **Maintenance: Comprehensive Testing**:
  - Added new test suites in `test/llm/tool_call/` for all new validation policies (`test_read_file_validation.py`, `test_read_files_validation.py`, `test_replace_in_file_validation.py`).

## 2.2.14

- **Improvement: Enhanced LLM Chat UI/UX**:
  - **Improved Clipboard Handling**: Added robust fallback to in-memory clipboard when `pyperclip` is unavailable, preventing crashes on systems without clipboard support.
  - **Better Navigation Controls**: Added F6 key to toggle focus between input and output fields, and improved Tab/Shift+Tab navigation between UI elements.
  - **Enhanced Output Field Scrolling**: Implemented proper cursor position preservation during content updates, ensuring smooth scrolling experience.
  - **Prevent Interruptions During Thinking**: Blocked new messages, custom commands, and execution commands while the LLM is processing, preventing state corruption.

- **Improvement: Keybinding & Input Refinements**:
  - **Smart Focus Management**: Modified printable character redirection to only occur when no text is selected in the output field, allowing text copying without losing selection.
  - **Better History Navigation**: Restricted Up/Down arrow history navigation to only work when no completion menu is visible, preventing conflicts with autocomplete.
  - **Enhanced Multiline Handling**: Improved handling of multiline inputs with trailing backslashes and better Enter key behavior.

- **Bug Fix: ANSI Escape Sequence Handling**:
  - **Robust Lexer Updates**: Enhanced the CLI style lexer to properly handle both real ESC characters (`\x1B`) and literal string representations (`\033`) in ANSI escape sequences.
  - **Accurate Banner Width Calculation**: Updated ASCII art banner generation to correctly calculate visible length excluding ANSI escape codes, ensuring proper alignment.

- **Improvement: ASCII Art & Visual Presentation**:
  - **Proper ANSI-Aware Padding**: Modified banner padding logic to account for ANSI escape sequences when calculating visual width, preventing misaligned ASCII art displays.
  - **Consistent Output Formatting**: Added global line prefix function to ensure consistent indentation of command outputs in the chat history.

## 2.2.13

- **Bug Fix: Robust Thinking Tag Removal**:
  - **Nested Tag Handling**: Fixed critical bug in thinking tag removal logic that incorrectly handled nested `<thinking>` tags. The original regex-based approach matched from the first opening tag to the first closing tag, causing nested content to be incorrectly preserved.
  - **New Utility Module**: Created `src/zrb/util/string/thinking.py` with `remove_thinking_tags()` function that uses a stack-based parser to properly handle nested tags, unclosed tags, and mixed `<thinking>`/`<thought>` tags.
  - **Comprehensive Testing**: Added 12 test cases covering all edge cases including nested tags, malformed XML, legitimate tag text in content, and performance with large text.
  - **Backward Compatibility**: Maintained existing behavior while fixing the core issue, ensuring all existing tests continue to pass.

- **Improvement: Summarizer Refactoring & Tool Pair Safety**:
  - **Modular Architecture**: Refactored monolithic `summarizer.py` (600+ lines) into a clean modular structure in `src/zrb/llm/summarizer/` with separate modules for chunk processing, history splitting, message conversion, message processing, and text summarization.
  - **Tool Pair Integrity**: Enhanced history splitting logic to NEVER break complete tool call/return pairs (Pydantic AI requirement). Added `validate_tool_pair_integrity()` function to detect and warn about broken tool pairs.
  - **Best-Effort Splitting**: When no perfect split exists, the system now uses a best-effort approach that minimizes damage while respecting Pydantic AI constraints.
  - **Increased Default Window**: Raised default `ZRB_LLM_HISTORY_SUMMARIZATION_WINDOW` from 30 to 100 messages for better context preservation.

## 2.2.12

- **Bug Fix: Corrupted Mandate Restoration**:
  - **Mandate.md Corruption Fix**: Restored missing content in `src/zrb/llm/prompt/markdown/mandate.md` that was corrupted by placeholder text ("...") in commit c8e077e6 ("Add feature/fix bug").
  - **Complete Section Restoration**: Recovered detailed thought block instructions and systematic workflow guidance from tag 2.2.9, merging them with improved delegation rules and examples from the current version.

## 2.2.11

- **Improvement: Thinking Tag Removal & Summarizer Robustness**:
  - **Robust Thinking Tag Removal**: Enhanced the thinking tag removal logic in `llm_task.py` to strip ANSI escape codes before removing `<thinking>` tags, ensuring reliable cleanup of internal reasoning blocks from agent responses.
  - **Summarizer Default Value Fix**: Added proper default value assignment for `summary_window` parameter in `summarizer.py`, preventing potential `None` value errors and improving stability of history summarization.
  - **Default Summarization Windows**: Change default summarization from 12 to 30

## 2.2.10

- **Improvement: Summarization & History Processing**:
  - **Robust Summarizer**: Major refactoring of the history summarization logic to improve stability and context retention.
  - **Stream Response Handling**: Enhanced handling of streaming responses during summarization to prevent interruptions.

- **Improvement: UI/UX & Visualization**:
  - **Enhanced Tool Visualization**: Improved the visual presentation of file operations (`write_file`, `replace_in_file`) in the chat interface, making code changes easier to review.
  - **Completion Rendering**: Refined the completion rendering logic in `completion.py` for a smoother user experience.
  - **Prompt Tweaks**: Minor updates to core prompts and mandates to align with visual improvements.

## 2.2.9

- **Feature: Enhanced Two-Tier Summarization System**:
  - **Conversational Summarizer**: Introduced a specialized agent for distilling entire conversation history into structured XML `<state_snapshot>` format, preserving critical context while dramatically reducing token usage.
  - **Message Summarizer**: Added a dedicated agent for summarizing individual large tool call results and messages, preventing token overflow from verbose tool outputs.
  - **Structured State Snapshots**: Implemented comprehensive XML-based state tracking with sections for goals, constraints, knowledge, reasoning summaries, artifact trails, and task states.

- **Improvement: Configuration Refinement**:
  - **Token Property Standardization**: Renamed token-related configuration properties from plural to singular for consistency (`LLM_MAX_TOKENS_PER_MINUTE` → `LLM_MAX_TOKEN_PER_MINUTE`, `LLM_MAX_TOKENS_PER_REQUEST` → `LLM_MAX_TOKEN_PER_REQUEST`).
  - **Granular Summarization Thresholds**: Added separate configuration options for conversational summarization (`LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD`) and message summarization (`LLM_MESSAGE_SUMMARIZATION_TOKEN_THRESHOLD`).
  - **Increased History Window**: Raised default history summarization window from 5 to 12 messages for better context preservation.

- **Improvement: History Processing & Stability**:
  - **Emergency Failsafe**: Added robust handling for cases where summarization fails to reduce history size below API limits, with automatic pruning to prevent crashes.
  - **Smart Message Merging**: Implemented safety checks to merge consecutive `ModelRequest` messages when appropriate, improving conversation flow.
  - **Enhanced Chunking Logic**: Added intelligent text chunking for extremely large tool results, ensuring reliable summarization of massive outputs.

- **Security & Reliability**:
  - **Prompt Injection Defense**: Added explicit security rules to summarizer prompts to ignore adversarial content and formatting instructions within chat history.
  - **Token Budget Enforcement**: Implemented strict token budget constraints for state snapshots (target <2000 tokens) to prevent system loops.
  - **Backward Compatibility**: Maintained support for legacy environment variable names while preferring new standardized forms.

## 2.2.8

- **Improvement: Enhanced Agent Reasoning & Planning**:
  - **Structured Thought Process**: Added mandatory `<thought>...</thought>` tags for internal reasoning before every response and tool call, improving transparency and decision-making quality.
  - **Systematic Workflow Refinement**: Enhanced the DEEP PATH workflow with explicit RESEARCH, STRATEGY, EXECUTION, and FINALITY phases for complex tasks.
  - **Bug Fix Methodology**: Added requirement to empirically reproduce failures with tests or scripts before applying fixes.

- **Improvement: Core Prompt Refinements**:
  - **Mandate Restructuring**: Reorganized mandate into logical sections: Internal Reasoning & Planning, Systematic Workflow, Communication & Delegation, Maintenance & Errors, and Context & Safety.
  - **Persona Enhancement**: Updated Senior Staff Engineer persona to prioritize maintainability over cleverness and always look for the "Standard Way" before inventing new solutions.
  - **Summarizer Enhancement**: Added `<reasoning_summary>` section to capture key logical deductions and architectural decisions from thought blocks.

- **Improvement: Operational Attitude**:
  - **Logical & Proactive Approach**: Added emphasis on thinking through architecture, identifying edge cases, and potential regressions before implementation.
  - **Security Emphasis**: Added explicit protection for `.env` and `.git` folders in security guidelines.
  - **Error Recovery**: Enhanced error handling with backtracking to Research or Strategy phase when a path fails.

## 2.2.7

- **Feature: Comprehensive Skill System**:
  - **Specialized Skill Definitions**: Added comprehensive skill definitions for common workflows including `commit`, `debug`, `init`, `plan`, `pr`, `research`, `review`, `skill-creator`, and `test`.
  - **Structured Workflows**: Each skill provides detailed, step-by-step guidance for executing specific tasks with proper verification and quality standards.
  - **User-Invocable Commands**: Skills are configured as user-invocable slash commands for direct access in the chat interface.

- **Improvement: Agent Delegation Protocol**:
  - **Enhanced Context Requirements**: Updated delegate tool documentation to emphasize that sub-agents are blank slates requiring full context (file contents, architectural details, environment info).
  - **Clearer Instructions**: Added explicit guidance for providing highly specific instructions when delegating to sub-agents.
  - **Mandate Alignment**: Updated core mandate to reflect the improved delegation protocol.

- **Refinement: Agent Definitions**:
  - **Coder Agent Enhancement**: Redefined as "Senior Software Engineer" with focus on code quality, safety, and rigorous verification. Added explicit "Read Before Writing" directive and improved Edit-Test-Fix loop guidance.
  - **Planner Agent Enhancement**: Redefined as "Systems Architect" with improved discovery phase guidance, risk analysis, and structured roadmap communication.
  - **Researcher & Reviewer Updates**: Enhanced agent descriptions and directives for better clarity and effectiveness.

- **Improvement: Documentation & Configuration**:
  - **LLM Integration Docs**: Updated configuration documentation for better clarity on LLM integration and rate limiting.
  - **Minor UI Tweaks**: Small improvements to TUI interface for better user experience.

## 2.2.6

- **Refactor: LLM Tool Standardization**:
  - **PascalCase Tool Names**: Renamed all LLM tools to use PascalCase aliases matching Claude standard conventions (e.g., `read_file` → `Read`, `write_file` → `Write`, `replace_in_file` → `Edit`).
  - **Tool Registry Cleanup**: Removed aliases and custom names from LLM tool registry, simplifying tool loading logic and improving consistency.
  - **Claude Compatibility**: Updated tool names to match Claude Code conventions for better interoperability.

- **Improvement: Core Documentation Restructuring**:
  - **Mandate Reorganization**: Completely restructured `mandate.md` with clearer organization into Context & Safety, Systematic Workflow, Communication & Delegation, and Maintenance & Errors sections.
  - **AGENTS.md Simplification**: Streamlined the agent guide to focus on practical development conventions and directory navigation.
  - **Enhanced Readability**: Improved documentation structure for better clarity and maintainability.

- **Dependency Management**:
  - **Termux Compatibility**: Limited `griffe` dependency to version < 2.0 for Termux compatibility, ensuring broader platform support.
  - **Dependency Updates**: Updated poetry.lock with refreshed dependency resolutions.

- **Configuration Updates**:
  - **Tool Policy Alignment**: Updated tool policies to match new PascalCase tool names.
  - **Agent Definition Updates**: Revised agent definitions to reference updated tool names and conventions.

## 2.2.5

- **Feature: Extended LLM Provider Support**:
  - **xAI Integration**: Added native support for xAI models via the new `xai` extra, providing access to Grok models through the official `xai-sdk`.
  - **Voyage AI Integration**: Added comprehensive support for Voyage AI embeddings and RAG capabilities via the new `voyageai` extra, including automatic dependency management.
  - **Dependency Updates**: Upgraded `pydantic-ai-slim` to `1.57.0` and `anthropic` to `>=0.78.0` for latest features and stability.
  - **Python Version Support**: Updated Python constraint to `<3.14.0` for forward compatibility.

- **Improvement: TUI Stability & Concurrency**:
  - **Message Queue System**: Implemented a robust job queue (`_message_queue`) to prevent overlapping AI responses and shell command execution, eliminating race conditions.
  - **Sequential Processing**: Ensures only one LLM task or shell command runs at a time, improving UI responsiveness and preventing state corruption.
  - **Better Trigger Handling**: Enhanced async iterator handling for external triggers with proper error isolation.

- **Improvement: Configuration & Performance**:
  - **Increased Token Limits**: Raised default `LLM_MAX_TOKENS_PER_MINUTE` from 120,000 to 128,000 to better accommodate modern model contexts.
  - **Extended Provider Configuration**: Added environment variable support for xAI and Voyage AI API keys and base URLs.

- **Refinement: Core Prompts & Agent Behavior**:
  - **Enhanced Persona**: Redefined as a "Polymath AI Assistant" with fluid expertise, adapting to coding (Senior Staff Engineer), writing (Creative Author), and research (Rigorous Analyst) contexts.
  - **Mandate Precision**: Added explicit style mimicry guidelines for both code (indentation, naming) and prose (tone, formatting).
  - **Knowledge Stewardship**: Mandated proactive use of note tools (`write_contextual_note`, `write_long_term_note`) to preserve learned patterns and preferences.
  - **Planning Rigor**: Expanded implementation guidance with context precision, import safety, and proofreading requirements.

- **Bug Fixes & Maintenance**:
  - **UI Cleanup**: Fixed resource cleanup on exit, properly cancelling message processor and ensuring queue drainage.
  - **Trigger Reliability**: Improved error handling in trigger loops to prevent cascading failures.
  - **Dependency Alignment**: Synchronized extras markers across `poetry.lock` for consistent optional dependency resolution.

## 2.2.4

- **Feature: Robust Hook System**:
  - **Claude Compatibility**: Full support for Claude Code-style declarative hooks with 100% event parity.
  - **Thread-Safe Execution**: Implemented a dedicated `HookExecutor` with built-in thread-safety and configurable timeouts for background operations.
  - **Advanced Matchers**: Added support for complex hook filtering using field matchers with multiple operators (regex, glob, contains, etc.).
  - **Expanded Hook Types**: Support for `Command`, `Prompt`, and `Agent` hooks with automatic environment injection.
  - **Comprehensive Documentation**: Added new guides for [Hook System](./hook-system.md) and [Quick Start](./hook-quickstart.md).
- **Improvement: TUI & UX Refinement**:
  - **Fluid Input**: The chat interface now supports empty inputs and better multi-line handling.
  - **Dynamic Keybindings**: Improved keybinding management and added new shortcuts for session control.
  - **Visual Stability**: Refined the main layout and UI components to prevent flickering and improve responsiveness.
- **Improvement: Agent Intelligence**:
  - **Context-Aware Summarization**: Optimized the history summarization agent to better preserve critical session details while reducing token usage.
  - **Extensible Tooling**: Enhanced the tool registry and delegate tool system to support more complex multi-agent workflows.
- **Bug Fixes**:
  - **Hook Reliability**: Resolved thread-safety issues in hook execution that previously caused intermittent TUI hangs.
  - **Summarization Fixes**: Corrected an issue where the summarization agent would occasionally lose context in long sessions.
  - **Claude Compatibility**: Fixed several edge cases in the Claude hook compatibility layer.

## 2.2.3

- **Bug Fix: TUI Broken Pipe**: Resolved a critical regression where asynchronous hook calls from background threads (e.g., stream capture) would crash the UI and cause `Broken pipe` errors.
- **Improvement: Trigger Visibility**: Added explicit error reporting and validation for external triggers (e.g., voice listen), ensuring that failures are no longer silently swallowed.

## 2.2.2

- **Feature: Dynamic Input Field**: The chat input area now dynamically adjusts its height based on the content (up to 10 lines), improving visibility for multi-line messages.
- **Improvement: TUI Layout Optimization**:
  - Redesigned the main interface to remove redundant framing around history, maximizing vertical space.
  - Enhanced scrolling logic to ensure the latest conversation markers are always correctly positioned.
  - Improved visual spacing and structural padding across the Title Bar, Info Bar, and Status Bar for a more modern, polished feel.

## 2.2.1

- **Bug Fix: ToolDenied Attribute Error**: Fixed an issue where the agent incorrectly attempted to access a non-existent `reason` property on `pydantic_ai.ToolDenied` objects. It now correctly uses the `message` attribute when executing `PostToolUseFailure` hooks.

## 2.2.0

- **Feature: Extensible Hook System**:
  - **Comprehensive Lifecycle Integration**: Implemented a robust hook system in `zrb.llm.hook` executing at all major agent and UI lifecycle points: `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PreCompact`, `SessionEnd`, `Notification`, and `Stop`.
  - **Claude Code Compatibility**: Native support for Claude Code-style declarative hooks (JSON/YAML) with automatic "hydration" into Python callables. Hooks are discovered from both `.claude/` and `.{ROOT_GROUP_NAME}/` directories.
  - **Python-Native Hooks**: Users can register arbitrary async Python functions as hooks directly via `hook_manager.register()`.
  - **Hook Management**: Centralized `HookManager` with automatic configuration loading, directory scanning, and prioritized execution.
  - **Tool Manipulation**: `PreToolUse` hooks can dynamically modify tool arguments or cancel execution entirely.

- **Improvement: Claude Code Ecosystem Compatibility**:
  - **Consolidated Documentation**: Added a new [Claude Code Compatibility](./advanced-topics/claude-compatibility.md) guide detailing Zrb's support for Claude-style Skills, Agents, Subagents, Hooks, and Project Instructions.
  - **Expanded Discovery**: Standardized search paths across Skills, Agents, and Hooks to respect both `.claude` and Zrb-specific configuration folders.

- **Improvement: TUI Responsiveness & Visual Stability**:
  - **Artifact-Free Rendering**: Implemented a background `_refresh_loop` and manual line centering with full-width padding in `ui.py` to eliminate rendering artifacts and "ghost" characters in the TUI header.
  - **Performance Optimization**: Reduced the `prompt_toolkit` refresh interval to `0.05s` for a significantly smoother user experience.
  - **UI Resiliency**: Improved error handling and state management within the TUI to prevent displacement during dynamic content updates.

- **Refactor: Logic Simplification & DRY Compliance**:
  - **Shared Utility Centralization**: Extracted duplicated path exclusion logic into a unified `is_path_excluded` utility in `zrb.util.file`, simplifying `list_files`, `glob_files`, and `analyze_code` tools.
  - **Todo Logic Optimization**: Refactored `select_todo_task` to remove redundant loop structures, improving code readability and performance.
  - **Architectural Standardization**: Updated `AGENTS.md` with "LLM Extension Architectural Patterns" to ensure consistent use of classic Python classes and module-level singletons.

- **Maintenance**:
  - **New Test Suite**: Added comprehensive test coverage for the hook system (`test/llm/hook/`).
  - **Configuration Expansion**: Added `ZRB_HOOKS_ENABLED`, `ZRB_HOOKS_DIRS`, `ZRB_HOOKS_TIMEOUT`, and `ZRB_HOOKS_LOG_LEVEL` environment variables.

## 2.1.0

- **Feature: Small Model Configuration**:
  - **LLM_SMALL_MODEL Support**: Added new configuration option `ZRB_LLM_SMALL_MODEL` for specifying a smaller/faster model for summarization and other auxiliary tasks. The `small_model` property is now available in `LLMConfig`.
  - **Enhanced Fuzzy Matching**: Improved fuzzy matching algorithm with boundary bonuses and subsequence penalties for better file path matching in autocompletion.
  
- **Improvement: Model Resolution & Provider Handling**:
  - **Built-in Provider Support**: Updated model resolution logic to properly handle built-in providers (DeepSeek, Ollama, Anthropic, Google, Groq, Mistral) without incorrectly transforming them to use OpenAI provider prefix.
  - **Summarizer Optimization**: Updated summarizer agent to automatically use `small_model` when no specific model is provided, improving efficiency for summarization tasks.
  
- **Bug Fix: Model Display Correction**:
  - **DeepSeek/Ollama Display**: Fixed issue where DeepSeek and Ollama models were incorrectly displayed with `openai:` prefix in the UI when `ZRB_LLM_MODEL` was set to `deepseek:model-name` or `ollama:model-name`.
  
- **Maintenance: Testing & Documentation**:
  - **Configuration Tests**: Added comprehensive tests for new `LLM_SMALL_MODEL` and `LLM_PLUGIN_DIRS` configuration options.
  - **Fuzzy Match Tests**: Added tests for improved fuzzy matching algorithm to ensure proper path matching behavior.

- **Breaking Changes**:
  - **Plugin Directory Configuration**: The environment variable `ZRB_LLM_PLUGIN_DIR` has been renamed to `ZRB_LLM_PLUGIN_DIRS` (plural). Users with custom plugin directories need to update their configuration.

## 2.0.19

- **Feature: Active Skills Support in LLM Tasks**:
  - **PromptManager Update**: Added `active_skills` (`StrListAttr`) and `render_active_skills` parameters to `PromptManager` for better control over which skills are loaded into the system prompt.
  - **LLMTask & LLMChatTask Update**: Added `active_skills` and `render_active_skills` parameters. These tasks now automatically instantiate a `PromptManager` if these parameters are provided, simplifying task configuration.
  - **Dynamic Resolution**: `PromptManager` now dynamically resolves `active_skills` from the context during prompt composition, allowing for conditional or dynamic pre-loading of skill content.

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