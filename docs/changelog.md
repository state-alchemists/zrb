🔖 [Documentation Home](../README.md)

## 2.20.2 (April 15, 2026)

- **Security: Dependency Vulnerability Patches**:
  - Updated `Pillow` from `>=10.0.0` to `>=12.2.0` (CVE-2026-40192: decompression bomb via unlimited GZIP read in FITS decoding).
  - Updated `pytest` from `^8.3.5` to `>=9.0.3` (CVE-2025-71176: local privilege escalation via `/tmp/pytest-of-{user}` directories).

- **Bug Fix: SharedContext Mutable Default Arguments**:
  - `SharedContext.__init__` changed mutable defaults (`={}`, `=[]`) to `None` with proper initialization, preventing shared state between instances.

- **Bug Fix: Session.get_root_tasks() Infinite Recursion**:
  - Replaced recursive `get_root_tasks()` with iterative traversal using a visited set to prevent infinite loops with cyclic task graphs.

- **Bug Fix: Session.terminate() Mutation During Iteration**:
  - Wrapped `dict.values()` and `list` iterations with `list()` to prevent "dictionary changed size during iteration" errors during session termination.

- **Bug Fix: State Logger CPU Consumption**:
  - Changed state logger sleep from `asyncio.sleep(0)` to `asyncio.sleep(0.1)`, capping writes at ~10 per second instead of spinning at full CPU.

- **Bug Fix: Builtin Plugin Path Resolution**:
  - Fixed `Path(os.path.dirname(__file__)).parent` to `Path(__file__).parent.parent.parent` for correct builtin path in `SkillManager`, `HookManager`, and `SubAgentManager`.

- **Refactoring: Modernize Type Annotations**:
  - Replaced `Optional[X]` → `X | None`, `Union[X, Y]` → `X | Y`, `Dict` → `dict`, `List` → `list`, `Tuple` → `tuple` across LSP, agent, prompt, and tool modules.

- **Refactoring: Path Handling Migration**:
  - Replaced `os.path.dirname(__file__)` + `os.path.join` with `Path(__file__).parent` / path operations across all web route modules and prompt loading.

- **Refactoring: Deduplicate Agent Search Directory Logic**:
  - Extracted `_add_agents_from_root()` method in `SubAgentManager` to eliminate repeated directory scanning code across user home, project, and base search sections.

- **Refactoring: Deduplicate Task Group Execution**:
  - Extracted `_execute_task_group()` and `_skip_task_group()` helper functions in `execution.py` to reduce duplication in successor/fallback execute and skip logic.

- **Refactoring: Deduplicate BaseTask Append Methods**:
  - Extracted `_append_unique_tasks()` method in `BaseTask` to consolidate `append_fallback`, `append_successor`, `append_readiness_check`, and `append_upstream`.

- **Refactoring: Deduplicate File List Truncation**:
  - Extracted `_truncate_file_list()` helper in `file.py` to share truncation logic between `list_files()` and `glob_files()`.

- **Documentation: New and Expanded Docs**:
  - New `docs/advanced-topics/mcp-support.md`: MCP server configuration and discovery guide.
  - Expanded `docs/advanced-topics/llm-integration.md`: Added "Built-in LLM Tools" reference section covering all built-in tool categories.
  - Expanded `docs/advanced-topics/maintainer-guide.md`: Added "Context Propagation Internals" section documenting `ContextVar` usage patterns.
  - Expanded `docs/advanced-topics/upgrading-guide.md`: Added "Upgrading from 1.x.x to 2.x.x" section with migration table.
  - Expanded `docs/core-concepts/session-and-context.md`: Added "Ambient Context" section documenting `get_current_ctx()` and `zrb_print()`.

- **Tests: Coverage Expansion**:
  - New `test/llm/lsp/test_lsp_protocol.py`: LSP protocol data structures (+345 lines).
  - New `test/llm/prompt/test_system_context.py`: System context prompt generation (+228 lines).
  - New `test/llm/tool_call/test_read_file_validation.py`: Read file validation (+48 lines).
  - New `test/llm/tool_call/test_replace_in_file_validation.py`: Replace-in-file validation (+96 lines).
  - New `test/llm/tool_call/tool_policy/test_auto_approve.py`: Auto-approve policy (+221 lines).
  - New `test/task/base/test_monitoring.py`: Task monitoring (+437 lines).
  - New `test/session/test_session.py`: Session lifecycle and root task detection (+145 lines).
  - Enhanced `test/task/base/test_execution.py`: Execution helpers and task group logic (+222 lines).
  - Enhanced `test/task/test_lifecycle.py`: State logger timing and lifecycle (+177 lines).
  - New `test/builtin/llm/test_chat_tool_policy.py`: Chat tool policy (+131 lines).
  - New `test/runner/web_route/test_task_input_api.py`, `test_logout_api_route.py`, `test/runner/web_schema/test_web_user_schema.py`, `test/llm/agent/test_common.py`, `test/util/test_util_group.py`, `test/input/test_base_input.py`.

- **Maintenance: Dependency Updates**:
  - Updated `poetry.lock` with latest compatible versions.

## 2.20.1 (April 13, 2026)

- **Improvement: Parallel Chunk Summarization**:
  - `chunk_and_summarize()` now runs all chunks concurrently via `asyncio.gather` instead of sequentially.
  - Up-front chunk building provides total count before launching tasks.
  - Progress indicator shows `Compressing chunk X/total (N messages)...`
  - Errors from individual chunks still propagate correctly.

- **Improvement: Tool Call Preparation Indicator**:
  - New static `🔄 Prepare tool parameters...` indicator on `PartStartEvent(ToolCallPart)`.
  - Providers that stream deltas (OpenAI, Anthropic) overwrite the static line with the animated spinner.
  - Providers that don't stream (e.g., Ollama) leave the static line visible for better feedback.
  - New `was_tool_call_start` flag ensures clean transitions between static and animated states.

- **Improvement: Worktree Repo-Local Storage**:
  - Worktrees now placed inside the repo under `.{ROOT_GROUP_NAME}/worktree/` instead of system temp directory.
  - Uses `git rev-parse --show-toplevel` to resolve the git repo root.
  - Keeps worktrees co-located with the repository they belong to.

- **Feature: Bidirectional Journal Graph**:
  - Journal restructured as a bidirectional graph with a backlinks protocol.
  - Every forward link must have a backlink entry in the target note's `## Backlinks` section.
  - New Link Convention with relative paths from the journal root.
  - Step-by-step guide for creating new notes with proper backlink maintenance.
  - Updated `journal_mandate.md` with embedded index context and retrieval guidance.
  - Updated `core-journaling` skill with backlink protocol, maintenance rules, and ~50-line file limit guidance.

- **Improvement: Active Skills Tracking in Summarizer**:
  - New `<active_skills>` section in the `conversational_summarizer.md` state snapshot XML.
  - Skills activated via `ActivateSkill` are now tracked and restored on context recovery.
  - Restored agent re-activates skills if the task still requires that domain expertise.

- **Improvement: Mandate Updates**:
  - Added "Memory Operations" as rule priority #4: journaling and skill activation are autonomous; exempt from Scope Discipline.
  - Marked Delegation and Skills sections with `*(if available)*` conditional markers.
  - Added `WriteMany`, `ClearTodos`, `ExitWorktree`, `ListWorktrees` to tool selection table.
  - Marked conditional tools with `*(if available)*` in the tool selection table.

- **Improvement: Tool Docstring Updates**:
  - `WriteTodos`: Replaced "Create todos before starting complex multi-step tasks" mandate with "Call `GetTodos` before each subtask to check current state".
  - `OpenWebPage`: Reformatted `MANDATE` to `MANDATES` with bulleted guidance.

- **Maintenance: Dependency Updates**:
  - Updated `pydantic-ai-slim` from `~1.76.0` to `~1.80.0`.
  - Updated `pydantic-graph` from `1.76.0` to `1.80.0` (transitive).
  - Updated `poetry.lock` with latest compatible versions.

## 2.20.0 (April 12, 2026)

- **Feature: Rewind/Snapshot System**:
  - New `SnapshotManager` class using shadow git repositories for filesystem snapshots.
  - `/rewind` command restores filesystem and conversation history to a previous state.
  - Snapshots track message count for consistent history restoration.
  - Config: `LLM_ENABLE_REWIND=on`, `LLM_SNAPSHOT_DIR`, `LLM_UI_COMMAND_REWIND`.
  - Default snapshot location: `~/.zrb/llm-snapshots/`.
  - New `enable_rewind` and `snapshot_dir` parameters on `LLMChatTask`.

- **Feature: PowerShell Autocomplete**:
  - New `zrb shell autocomplete powershell` command generates PowerShell completion script.
  - Native `Register-ArgumentCompleter` integration for dynamic CLI completion.
  - Mirrors bash completion behavior with proper partial word handling.

- **Feature: Configurable Magic Numbers**:
  - All timeout, interval, size, and retry values now configurable via environment variables.
  - Timeout configs (milliseconds): `LLM_SSE_KEEPALIVE_TIMEOUT`, `LLM_REQUEST_TIMEOUT`, `LLM_WEB_PAGE_TIMEOUT`, etc.
  - Interval configs (milliseconds): `LLM_UI_STATUS_INTERVAL`, `LLM_UI_REFRESH_INTERVAL`, `SCHEDULER_TICK_INTERVAL`, etc.
  - Size/Limit configs: `LLM_MAX_COMPLETION_FILES`, `LLM_FILE_READ_LINES`, `LLM_MAX_OUTPUT_CHARS`, etc.
  - Retry configs: `LLM_MAX_CONTEXT_RETRIES`, `LLM_TOOL_MAX_RETRIES`, `LLM_MCP_MAX_RETRIES`.
  - Pagination configs: `WEB_SESSION_PAGE_SIZE`, `WEB_API_PAGE_SIZE`.

- **Feature: Model Visibility Controls**:
  - `LLM_SHOW_OLLAMA_MODELS`: Enable/disable Ollama models in `/model` autocomplete.
  - `LLM_SHOW_PYDANTIC_AI_MODELS`: Enable/disable pydantic-ai built-in models in autocomplete.
  - Useful for environments without Ollama or when using custom model registries.

- **Breaking Change: Hooks Timeout Unit**:
  - `HOOKS_TIMEOUT` changed from seconds (30) to milliseconds (30000).
  - Existing configs with `ZRB_HOOKS_TIMEOUT=30` will now timeout after 30ms.
  - Update your config to `ZRB_HOOKS_TIMEOUT=30000` for equivalent behavior.

- **Improvement: Documentation**:
  - Expanded `docs/configuration/llm-config.md` with all configurable timeout/interval/size values.
  - Added detailed descriptions for new environment variables.

- **Tests: Coverage Expansion**:
  - New `test/llm/snapshot/test_manager.py`: Snapshot manager tests (+367 lines).
  - New `test/llm/tool/test_file.py`: File tool tests (+313 lines).
  - New `test/llm/prompt/test_claude.py`: Claude prompt tests (+398 lines).
  - New `test/config/test_config.py`: Config property tests (+278 lines).
  - New `test/llm/util/test_history_formatter.py`: History formatter tests (+145 lines).
  - Enhanced SSE stream, completion, and command tests.

# Older Changelog

- [Changelog v2](./changelog-v2.md)
- [Changelog v1](./changelog-v1.md)