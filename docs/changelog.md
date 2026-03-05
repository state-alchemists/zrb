🔖 [Documentation Home](../README.md)

## 2.7.0 (March 5, 2026)

- **Major: Core Prompt System Simplification & Mandate Restructuring**:
  - **Project Context Prompt Overhaul**: Completely redesigned `src/zrb/llm/prompt/claude.py` to provide clear "Project Documentation Guidelines" instead of attempting to summarize documentation files. The new approach lists available documentation files with status indicators and provides SMART documentation usage rules for LLMs.
  - **Mandate Simplification**: Streamlined all core mandate files with clearer, more direct language:
    - **Git Mandate**: Restructured as "🐙 Absolute Git Rule" with clear prohibitions, approval protocol, and violation response. Removed verbose examples in favor of concise, actionable rules.
    - **Journal Mandate**: Restructured as "📓 Absolute Journaling Rule" with clear activation requirements, smart reading guidelines, and update guidelines. Emphasizes journal as single source of truth.
    - **Core Mandate**: Reorganized into clear "Core Directives" focusing on Plan Before Acting, Context-First, Empirical Verification, Clarify Intent, Context Efficiency, Secret Protection, and Self-Correction.
  - **Prompt Placeholder Enhancement**: Updated `src/zrb/llm/prompt/prompt.py` to include file existence status indicators (`{CFG_LLM_JOURNAL_DIR_STATUS}` and `{CFG_LLM_JOURNAL_INDEX_FILE_STATUS}`) and improved journal content handling with truncation for large files.

- **Improvement: Summarizer Configuration Simplification**:
  - **Default History Processor**: Simplified summarizer usage across the system by removing explicit token threshold and summary window parameters in favor of default configuration. Updated `src/zrb/builtin/llm/chat.py`, `src/zrb/llm/agent/manager.py`, and `src/zrb/llm/task/llm_chat_task.py` to use `create_summarizer_history_processor()` without parameters.
  - **History Splitter Logic Update**: Modified `src/zrb/llm/summarizer/history_splitter.py` to use `summary_window` parameter directly instead of calculating retention ratio, improving clarity and consistency.

- **Cleanup: Removal of Unused Thinking Tag Utilities**:
  - **Code Removal**: Removed `src/zrb/util/string/thinking.py` and `test/util/string/test_thinking.py` as the thinking tag removal functionality was no longer being used in `src/zrb/llm/task/llm_task.py`.
  - **Simplified Output Processing**: Updated `LLMTask._clean_output()` to only remove ANSI escape codes, eliminating unnecessary processing step for thinking tags.

- **Dependency Updates**:
  - **Core Framework**: pydantic-ai-slim updated from ~1.63.0 to ~1.65.0, bringing latest improvements and bug fixes from the pydantic-ai framework.

- **Maintenance**:
  - **Version Bump**: Updated to version 2.7.0 in `pyproject.toml`, marking a significant release with major prompt system improvements.

# Older Changelog

- [Changelog v2](./changelog-v2.md)
- [Changelog v1](./changelog-v1.md)

