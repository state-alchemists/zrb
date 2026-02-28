🔗 [Home](../../README.md) > [Documentation](../README.md) > [Changelog](README.md)

## 2.6.20 (February 28, 2026)

- **Improvement: Enhanced Truncation Algorithm with Character Limit Support**:
  - **Multi-Stage Truncation Algorithm**: Enhanced `truncate_output` function in `src/zrb/util/truncate.py` with comprehensive character limit support following a multi-stage algorithm: (1) If content ≤ max_chars, return as-is; (2) Apply max_line_length truncation to all lines first; (3) If still > max_chars and line count > head_lines + tail_lines, remove lines from middle; (4) If still > max_chars, remove lines from tail (from top of tail section); (5) If still > max_chars, remove lines from head (from bottom of head section); (6) Insert truncation message only at end at location of removed lines.
  - **Character Truncation as Last Resort**: Added character-level truncation as final fallback with proper size accounting (available_for_content = max_chars - message_size) and edge case handling for very small max_chars (<15) returning minimal "..." indicator.
  - **Accurate Truncation Metadata**: Enhanced function to return tuple `(truncated_string, TruncationInfo)` with accurate truncation metrics (original/truncated lines/chars, omitted lines/chars, truncation_type) for precise truncation notices in tool outputs.
  - **Refactored for Maintainability**: Broke down 200+ line monolithic function into 7 focused helper functions (`_truncate_line`, `_apply_line_length_truncation`, `_remove_lines_from_middle`, `_remove_lines_from_tail`, `_remove_lines_from_head`, `_build_result_with_truncation_message`, `_apply_character_truncation`) while preserving exact algorithm and public API.

- **Improvement: Web Authentication Configuration Standardization**:
  - **Environment Variable Consistency**: Standardized web authentication environment variables: `ZRB_WEB_SECRET` → `ZRB_WEB_SECRET_KEY`, `ZRB_WEB_ACCESS_TOKEN_EXPIRE_MINUTES` → `ZRB_WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES`, `ZRB_WEB_REFRESH_TOKEN_EXPIRE_MINUTES` → `ZRB_WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES`.
  - **Configuration Property Updates**: Updated `Config` class properties and setters in `src/zrb/config/config.py` to match new environment variable names while maintaining backward compatibility through proper environment variable mapping.
  - **Documentation Updates**: Updated configuration documentation in `docs/installation-and-configuration/configuration/README.md`, `docs/installation-and-configuration/configuration/llm-integration.md`, and `docs/installation-and-configuration/configuration/web-auth-config.md` to reflect new variable names and provide clearer guidance.

- **Improvement: Enhanced Prompt Customization Hierarchy**:
  - **Multi-Level Prompt Override System**: Enhanced prompt loading in `src/zrb/llm/prompt/prompt.py` with four-level hierarchy: (1) `ZRB_LLM_PROMPT_DIR` (highest priority), (2) Environment variable direct override (`ZRB_LLM_PROMPT_{name}`), (3) `ZRB_LLM_BASE_PROMPT_DIR` (organization-wide), (4) Package default (lowest priority).
  - **New Configuration Option**: Added `ZRB_LLM_BASE_PROMPT_DIR` environment variable and `Config.LLM_BASE_PROMPT_DIR` property for organization-wide prompt overrides that apply across multiple projects.
  - **Documentation Enhancement**: Updated LLM integration documentation with clear search order explanation and examples for multi-level prompt customization.

- **Improvement: Core Mandate & Skill System Refinements**:
  - **Mandate Restructuring**: Reorganized `mandate.md` with clearer Universal Principles (Structured Thinking, Context-First, No Destructive Assumptions) and Absolute Directives focusing on secret protection and self-correction.
  - **Git Mandate Strengthening**: Enhanced `git_mandate.md` with "ABSOLUTE RULES" format, explicit prohibition examples, and strict approval protocol emphasizing "Assist, don't autonomously manage git."
  - **Skill System Consolidation**: Consolidated and renamed skills for better clarity: `core_journal` → `core_journaling`, `test` → `quality_assurance`, `research` → `research_and_plan`, `debug` → integrated into `quality_assurance`, removed redundant skills (`commit`, `core_mandate_brownfield`, `core_mandate_documentation`, `plan`, `pr`).
  - **Agent Simplification**: Consolidated multiple specialized agents into single `subagent.agent.md` for general delegation tasks, removing `coder.agent.md`, `explorer.agent.md`, `planner.agent.md`, `researcher.agent.md`, `reviewer.agent.md`.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.6.20 in `pyproject.toml`.
  - **Test Updates**: Updated `test/config/test_config.py` to reflect new environment variable names for web authentication configuration.

## 2.6.19 (February 27, 2026)

- **Improvement: Reusable Truncation Logic**:
  - **Centralized Logic**: Extracted line-length limit and head/tail preservation logic into `truncate_output` in `src/zrb/util/truncate.py`.
  - **Tool Consolidation**: Refactored `Grep`, `Read`, and `Bash` tools to import and use this shared utility, ensuring consistent and robust output truncation across the system.

- **Fix: Unbounded Line Lengths in Tool Outputs**:
  - **Grep Tool Truncation**: Addressed issue where matching against massive single-line files (e.g., minified JS or JSON dumps) would return megabytes of data. `_get_file_matches` in `src/zrb/llm/tool/file.py` now enforces a 1,000-character limit per line.
  - **Bash Tool Truncation**: Similarly updated `src/zrb/llm/tool/bash.py` to prevent giant single-line outputs from bloating the history.
  - **Read Tool Truncation**: Updated `read_file` to ensure individual lines are safely truncated when returning specific file line ranges.

- **Fix: Tool Execution Rejection Reason Truncation**:
  - **Preserved User Context**: Removed the hardcoded 500-character truncation limit for user rejection reasons in `src/zrb/llm/tool_call/handler.py`. Detailed feedback and code snippets provided during tool execution rejection are now passed to the AI exactly as is.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.6.19 in `pyproject.toml`.

## 2.6.18 (February 27, 2026)

- **Optimization: System Prompt Token Efficiency & Directive Strength**:
  - **Comprehensive Prompt Optimization**: Reduced system prompt from ~7K to ~5.8K tokens (17% overall reduction) while maintaining all critical directives and enforcement strength.
  - **Mandate.md Optimization**: Reduced from ~1,500 to ~800 tokens (47% reduction) by removing redundancies, tightening language, and eliminating filler while preserving Brownfield Protocol, Execution Framework, and safety directives.
  - **Persona.md Optimization**: Reduced from ~300 to ~200 tokens (33% reduction) with concise phrasing while maintaining "Brownfield Specialist" and "Pragmatic Doer" core identity.
  - **Journal Mandate Optimization**: Reduced from ~500 to ~350 tokens (30% reduction) by removing redundant phrasing and tightening "When to Read/Update" sections while keeping critical timing rules.
  - **Git Mandate Optimization**: Reduced from ~400 to ~280 tokens (30% reduction) by shortening verbose operation lists and consolidating "Core Principles" with tighter phrasing.
  - **Brownfield Protocol Analysis**: Documented AI's "knowing-doing gap" violation of mandate 2.2 (not activating core_mandate_brownfield before codebase work) and strengthened enforcement language.

- **Improvement: Token Estimation Accuracy**:
  - **Char-to-Token Ratio Correction**: Updated fallback token estimation from `char // 3` to `char // 4` in `LLMLimiter._count_tokens()` for more accurate token counting when tiktoken is not available.
  - **Truncation Logic Update**: Changed `truncate_text()` fallback from `max_tokens * 3` to `max_tokens * 4` to match the improved character-to-token ratio.
  - **Test Updates**: Updated test expectations in `test_limiter_coverage.py` and `test_limiter_explosion.py` to reflect the more accurate token estimation.

- **Improvement: Sequential Execution Enforcement**:
  - **Strategic Tool Selection**: Emphasized surgical tool usage with conservative limits and scopes for better context efficiency.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.6.18 in `pyproject.toml`.

## 2.6.17 (February 26, 2026)

- **Fix: Summarizer Brittle String Prefix Detection & Tool Denial Leakage**:
  - **Robust Type-Based Detection**: Replaced brittle string prefix checking in `src/zrb/llm/summarizer/message_processor.py` with type-based detection using `isinstance(safe_content, (ToolDenied, ToolApproved))` from pydantic_ai. This prevents summarization failures when tool denial/approval message wording changes.
  - **Module-Level Constants**: Added `SUMMARY_PREFIX = "SUMMARY OF TOOL RESULT:"` and `TRUNCATED_PREFIX = "TRUNCATED TOOL RESULT:"` as module-level constants, eliminating hardcoded string matching and ensuring consistent prefix usage across generation and detection.
  - **Tool Denial Message Handling**: Enhanced summarizer to skip processing for tool denial/approval messages, preventing wasted processing time on non-tool-result content.
  - **Uppercase Prefix Standardization**: Updated all prefix strings to uppercase format for consistency and clarity.

- **Fix: Tool Confirmation Output Leakage Prevention**:
  - **Buffer Clearance After Tool Confirmation**: Added `self._capture.clear_buffer()` in a `finally` block in `UI.confirm_tool_call()` (`src/zrb/llm/app/ui.py`) to prevent captured stdout from previous operations leaking into future tool results.
  - **User Response Truncation**: Added 500-character limit for user responses in tool confirmation prompts (`src/zrb/llm/tool_call/handler.py`) with truncation notification to prevent excessively long responses from overwhelming the system.

- **Improvement: Core Mandate Task Cancellation Protocol**:
  - **Explicit Cancellation Rules**: Added Task Cancellation section to `mandate.md` with clear rules: (1) Stop when user asks to cancel, (2) Immediate cessation of all tool calls and task execution, (3) No persistence with verification or completion attempts after cancellation.
  - **Tool Denial Response Enforcement**: Enhanced journal documentation with explicit "Tool Denial Response" preference requiring immediate cessation of tool calls when user denies execution with any message.

- **Test Updates**:
  - **Prefix Consistency**: Updated test expectations in `test/llm/summarizer/test_dual_threshold.py` and `test/llm/history_processor/test_history_summarizer.py` to expect uppercase prefixes (`SUMMARY OF TOOL RESULT:` instead of `SUMMARY of tool result:`).
  - **Comprehensive Validation**: All 49 summarizer-related tests pass with updated architecture.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.6.17 in `pyproject.toml`.

## 2.6.16 (February 26, 2026)

- **Fix: Thread-Safe Interactive Input Handling**:
  - **Graceful Interruption**: Refactored `StdUI.ask_user()` in `src/zrb/llm/agent/std_ui.py` to use `prompt_toolkit.PromptSession().prompt_async()` instead of `asyncio.to_thread(input)`. This prevents the application from hanging indefinitely when a user presses `Ctrl+C` (KeyboardInterrupt) during non-interactive mode tool confirmations. The previous thread-based implementation swallowed signals and blocked the shutdown process.
  - **EOF Error Handling**: Added proper handling for `EOFError` during input, returning an empty string to allow graceful fallback instead of crashing the process.

- **Test Infrastructure Updates**:
  - **Model Mocking**: Fixed an integration test that relied on live API calls by properly mocking the model `openai:gpt-4o-mini` to `test` in `test_tool_policy_integration.py`, preventing timeout errors on network interruptions.
  - **Assertion Resilience**: Updated assertions in `test_llm_task_tool_confirmation.py` to correctly evaluate dynamically wrapped callbacks during tool confirmation tests.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.6.16 in `pyproject.toml`.

## 2.6.15 (February 26, 2026)

- **Improvement: Core Prompt Refinements & Agent Identity Enhancement**:
  - **Mandate Restructuring**: Updated `mandate.md` with clearer CONTEXT EFFICIENCY principles, better distinction between Directives (action requests) and Inquiries (analysis requests), and improved Execution Framework with explicit Research → Strategy → Execution flow.
  - **Persona Enhancement**: Enhanced `persona.md` with "interactive CLI agent" identity, added High-Signal Output principles (avoid conversational filler, focus on intent), Concise & Direct communication style (aim for <3 lines per response), and Explain Before Acting requirement for state-modifying actions.
  - **Journal Mandate Clarification**: Improved `journal_mandate.md` with clearer guidance on when to read/update journal, emphasis on state snapshots and active constraints, and refined journal curation principles.

- **Improvement: Skill System Overhaul with Validation-First Philosophy**:
  - **Test Skill Enhancement**: Major overhaul of test skill with emphasis on "Validation is the only path to finality" mandate. Added detailed Environment & Pattern Audit workflow, comprehensive test generation guidelines, and Exhaustive Verification requirements (build, lint, type-check in addition to tests).
  - **Debug Skill Refinement**: Enhanced debug skill with Empirical Reproduction First mandate, structured scientific workflow, and improved debugging checklist focusing on empirical verification and surgical fixes.
  - **Brownfield Skill Updates**: Various refinements to core_mandate_brownfield skill for better discovery and execution protocols.

- **Improvement: Tool Safety & Non-Interactive Execution**:
  - **Bash Tool Safety Enhancement**: Added mandate to ALWAYS prefer non-interactive flags (`-y`, `--yes`, `--watch=false`, `CI=true`) for scaffolding tools or test runners to avoid persistent watch modes hanging execution.
  - **Improved Timeout Guidance**: Enhanced timeout error messages with specific guidance on using non-interactive flags to prevent background process issues.

- **Improvement: Agent Guidance Refinements**:
  - **Coder Agent Updates**: Enhanced guidance for safe integration into complex legacy codebases with emphasis on pattern matching and surgical changes.
  - **Generalist & Researcher Agent Refinements**: Updated agent guidance with improved workflow patterns and context efficiency principles.

- **Dependency Updates**:
  - **Core Framework**: pydantic-ai-slim updated from 1.62.0 to 1.63.0.
  - **LLM Providers**: anthropic (>=0.78.0 → >=0.80.0), cohere (>=5.18.0 → >=5.20.6), huggingface-hub (>=0.33.5,<1.0.0 → >=1.3.4,<2.0.0), voyageai (>=0.3.2 → >=0.3.7).
  - **Various transitive dependencies** updated for security and compatibility.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.6.15 in `pyproject.toml`.

## 2.6.14 (February 26, 2026)

- **Fix: Non-Interactive UI Tool Confirmation for Edit Command**:
  - **ToolCallHandler Integration**: Fixed editing in non-interactive mode by replacing simple policy checker with `ToolCallHandler` in `LLMChatTask._create_llm_task_core()`. The previous implementation used `check_tool_policies()` which only handled tool policies, not response handlers or argument formatters.
  - **Complete Tool Handling**: The fix switches to `ToolCallHandler` which properly handles all three components (tool policies, argument formatters, response handlers) and includes the 'e' (edit) option in the confirmation prompt.
  - **Key Change**: In `src/zrb/llm/task/llm_chat_task.py`, non-interactive mode now uses `ToolCallHandler(tool_policies=self._tool_policies, argument_formatters=self._argument_formatters, response_handlers=self._response_handlers)` instead of a simple async wrapper around `check_tool_policies()`.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.6.14 in `pyproject.toml`.

## 2.6.13 (February 25, 2026)

- **Improvement: SearxNG Configuration Refactoring & Automatic Management**:
  - **Streamlined Configuration File**: Remove `settings.yml` searxng file.
  - **Automatic Configuration Setup**: Added `copy_searxng_setting` task that automatically copies SearxNG configuration to `~/.config/searxng/` directory if it doesn't exist, ensuring proper configuration management without manual intervention.
  - **Improved Docker Volume Mounting**: Changed working directory from project directory to user home directory (`os.path.expanduser("~")`) for better Docker volume mounting compatibility, allowing the `./config/` volume to correctly map to the user's configuration directory.
  - **Task Integration**: Made `copy_searxng_setting` an upstream dependency of the `start-searxng` task, ensuring configuration is always available before starting the SearxNG container.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.6.13 in `pyproject.toml`.

## 2.6.12 (February 24, 2026)

- **Improvement: UI Output Redirection Buffering**:
  - **Buffered Stream Capture**: Modified `GlobalStreamCapture` in `src/zrb/llm/app/redirection.py` to buffer stdout/stderr output instead of immediately sending to UI via `ui_callback`. Added `_buffer` list, `get_buffered_output()`, and `clear_buffer()` methods for controlled output management.
  - **Delayed Output Display**: Updated `run_async()` in `src/zrb/llm/app/ui.py` to print buffered output after UI closes (`self._capture.stop()`), providing cleaner UI experience with output appearing after interaction completion.
  - **Tool Streaming Preservation**: Bash tool output continues to stream to UI in real-time via `zrb_print(..., plain=True)` → `append_to_output` direct path (bypasses capture), maintaining responsive tool feedback while buffering library `print()` output.

- **Fix: Hook System Error Handling & Sequential Execution**:
  - **Proper Error Propagation**: Updated `_parse_hook_result()` in `src/zrb/llm/hook/executor.py` to set `error=result.output` and `exit_code=1` when `success=False`, ensuring proper error reporting for failed hook executions.
  - **Sequential Hook Execution**: Changed `execute_hooks()` in `src/zrb/llm/hook/manager.py` from concurrent (`asyncio.gather`) to sequential execution, enabling proper blocking behavior and `continue_execution=False` logic to work correctly.
  - **Enhanced Hook Result Processing**: Improved error handling with proper exception wrapping and continuation logic for failed hooks, maintaining Claude Code compatibility with exit code 2 for blocking decisions.

- **Test Infrastructure: Comprehensive Test Suites**:
  - **OptionInput Test Coverage**: Created comprehensive test suite for `OptionInput` in `test/input/test_option_input.py` with 7 test cases covering public API (initialization, HTML generation, default values, context updates), improving coverage from 25% to 40%.
  - **Lexer ANSI Escape Testing**: Added comprehensive test suite for `CLIStyleLexer` in `test/llm/app/test_lexer.py` with 13 tests covering ANSI escape sequence tokenization (colors, bold, background colors, reset sequences, literal escapes).
  - **Redirection Buffer Testing**: Created comprehensive test suite for `GlobalStreamCapture` in `test/llm/app/test_redirection.py` with 8 test cases covering public API (initialization, start/stop lifecycle, buffer management, pause context manager, original stdout retrieval).
  - **Hook Manager Comprehensive Coverage**: Added extensive test suite in `test/llm/hook/test_manager_comprehensive_coverage.py` with 49 tests covering edge cases, error handling, blocking logic, timeout scenarios, and Claude Code compatibility.

- **Test Results**: All 866 tests pass with 31% overall coverage. Hook test suite passes 49/49 tests after fixes.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.6.12 in `pyproject.toml`.

## 2.6.11 (February 24, 2026)

- **Refactor: Centralized String Conversion Utility**:
  - **Shared to_string() Function**: Created centralized `to_string()` utility in `src/zrb/util/string/conversion.py` to handle complex data structure conversion to strings with proper JSON serialization for dictionaries and lists.
  - **Eliminated Code Duplication**: Removed `FileHistoryManager._convert_to_string()` method and replaced all `str()` calls in tool return content with `to_string()` for consistent string conversion behavior.
  - **Enhanced Tool Return Safety**: Updated `_create_safe_wrapper()` and `_wrap_toolset()` in `src/zrb/llm/agent/common.py` to use `to_string()` for tool return content, ensuring proper handling of non-string tool results.
  - **Proactive Content Cleaning**: Enhanced `FileHistoryManager._clean_corrupted_content()` to use centralized `to_string()` utility, maintaining proactive cleaning of boolean, number, dict, list, and None values before validation.
  - **JSON Serialization Safety**: The new utility safely handles dictionaries and lists via `json.dumps()` with proper error fallback to `str()` for serialization failures.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.6.11 in `pyproject.toml`.

# Older Changelog

- [Changelog v2](./changelog-v2.md)
- [Changelog v1](./changelog-v1.md)

🔗 [Home](../../README.md) > [Documentation](../README.md) > [Changelog](README.md)
