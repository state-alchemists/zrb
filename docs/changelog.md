🔖 [Documentation Home](../README.md)

## 2.10.1 (March 14, 2026)

- **Refactor: Streamlined Prompt System**:
  - Converted `mandate.md` and `journal_mandate.md` to concise table-based formats, reducing visual noise while preserving all rules.
  - Added explicit "Decision Flow" section to mandate with ordered delegation check, skill activation, and execution steps.
  - Added tier-aligned journal scope: Tier 1 skips journaling entirely, Tier 2 journals only on discoveries.
  - Condensed project context rules in `claude.py` from 25 lines to 10 lines with clear documentation hierarchy.

- **Refactor: Improved Delegate Tool Documentation**:
  - Unified terminology: `subagent` instead of `sub-agent` throughout tool docstrings.
  - Simplified docstring format with "USAGE" bullets pointing to mandate for delegation rules.
  - Reference to mandate Section 5 for "WHEN TO USE" guidance.

- **Refactor: Lazy Skill Manager Initialization**:
  - Removed `auto_load` parameter from `SkillManager.__init__`.
  - Added `_ensure_scanned()` method for lazy initialization on first access.
  - Reduces startup overhead when skills aren't immediately needed.

- **Refactor: Agent Naming**:
  - Renamed agent from `subagent` to `generalist` for clearer semantic meaning.
  - File renamed from `subagent.agent.md` to `generalist.agent.md`.

- **Fix: Persona Delegation Wording**:
  - Updated "Delegate only for exceptional scale" to "Delegate when context isolation is beneficial."
  - Corrects overly narrow guidance about when to delegate.

## 2.10.0 (March 12, 2026)

- **Feature: Grep Timeout Parameter**:
  - Added `timeout` parameter to `Grep` tool in `src/zrb/llm/tool/file.py`, allowing users to set a maximum execution time for search operations. This prevents long-running regex searches from blocking the agent indefinitely.

- **Feature: Parallel Agent Delegation**:
  - Enhanced `DelegateToAgent` tool in `src/zrb/llm/tool/delegate.py` to support parallel execution of multiple sub-agents, significantly improving performance for batch processing workflows.
  - Added `tool_factories` and `toolset_factories` support to `LLMTask`, enabling dynamic tool resolution at execution time.
  - Updated SubAgent system prompts and improved context handling for delegated tasks.

- **Refactor: Replace python-jose with PyJWT**:
  - Migrated JWT handling from `python-jose` to `PyJWT` in `src/zrb/runner/web_util/token.py` and `src/zrb/runner/web_util/user.py`.
  - PyJWT is a more focused, actively maintained library specifically for JWT operations.
  - Updated `pyproject.toml` dependency from `python-jose[cryptography]` to `PyJWT ^2.8.0`.

- **Refactor: Reduce Cyclomatic Complexity in Hook Matcher**:
  - Refactored `_evaluate_matchers` in `src/zrb/llm/hook/manager.py` from a 23-branch if/elif chain to a clean dispatch dictionary pattern.
  - Each matcher operator (EQUALS, NOT_EQUALS, CONTAINS, STARTS_WITH, ENDS_WITH, REGEX, GLOB) now has its own focused module-level function.
  - Improved maintainability: Adding new operators now simply requires extending the `_MATCHER_OPERATORS` dictionary.

- **Maintenance: Code Formatting and Test Coverage**:
  - Applied consistent code formatting across multiple files.
  - Added extensive test coverage for callbacks, commands, input handling, LLM agents, and delegate tools.

# Older Changelog

- [Changelog v2](./changelog-v2.md)
- [Changelog v1](./changelog-v1.md)

