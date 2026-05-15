🔖 [Documentation Home](../README.md)


## 2.28.2a1 (May 15, 2026)

- **Improvement: Journal mandate wording tightened + rationale added**:
  - `journal_mandate.md`: Changed "decided between approaches" to "created significant decision" in the activity-log trigger — more precise about what warrants a log entry (decisions that change direction, not every binary choice).
  - Added a "Why 'before reply'?" section explaining that a finding not logged before replying is lost if the session closes. Deferring is equivalent to discarding.

## 2.28.1 (May 15, 2026)

- **Bug Fix: `[build-system]` typo in `pyproject.toml`**:
  - Key `build-system` inside the `[build-system]` table renamed to `build-backend` per PEP 517 spec. This was causing `BuildSystemTableValidationError` when installing the package via Poetry/pip.

## 2.28.0 (May 15, 2026)

- **Breaking: `PromptManager` simplified to single `include_sections` param**:
  - `PromptManager.__init__()`: 9 individual `include_*` boolean flags (`include_persona`, `include_mandate`, `include_git_mandate`, `include_system_context`, `include_journal_mandate`, `include_claude_skills`, `include_cli_skills`, `include_project_context`, `include_tool_guidance`) replaced by a single `include_sections: list[str] | None` parameter. All 9 corresponding properties removed.
  - New `CFG.LLM_INCLUDE_SECTIONS` config list drives prompt section composition by default; instance-level `include_sections` override wins.
  - Removed from `zrb.llm.prompt`: `get_persona_prompt()`, `get_mandate_prompt()`, `get_git_mandate_prompt()`, `get_journal_prompt()`, `get_summarizer_system_prompt()`, `get_file_extractor_system_prompt()`, `get_repo_extractor_system_prompt()`, `get_repo_summarizer_system_prompt()`, `create_cli_skills_prompt()`. Consolidated into `get_prompt(name, **extra_replacements)`.
  - Removed `zrb.llm.prompt.cli` module (`create_cli_skills_prompt`).
  - Removed `chat_tool_policy.py` support for batch `paths`/`files` approval (WriteMany).

- **Breaking: ReadMany/WriteMany batch tools removed**:
  - Removed `read_files`, `write_files` tool functions, `WriteMany`/`ReadMany` auto-approve policies, `write_files_formatter`, and `read_files_validation_policy`. `Read`/`Write` handles multiple files via parallel calls or chunked writes.
  - `docs/advanced-topics/llm-integration.md` updated to remove `ReadMany`/`WriteMany` from the tools table.

- **Breaking: Tool-call internals trimmed**:
  - Removed `tool_call/argument_formatter/write_file_formatter.py` and `tool_call/tool_policy/read_files_validation.py`.
  - `zrb.llm.tool_call` exports reduced accordingly.

- **Feature: History retention + backup rotation**:
  - New `_retry_prompt_to_text()` helper; history sanitization now gated behind `DEBUG` logging for performance.
  - New `_safe_int_from_env()` helper in `LLMContentMixin` deduplicates `int(get_env(...))` pattern across 5 properties.
  - New `CFG.LLM_HISTORY_BACKUP_RETAIN` (default `3`) controls how many timestamped backups are kept per conversation. Set to `-1` to keep all (legacy behavior) or `0` to disable backups.
  - `file_history_manager.py`: Backup rotation now sorts by filename (lexicographic = chronological for ISO-8601 timestamps) instead of mtime — deterministic on coarse filesystems (FAT32, Docker overlayfs).
  - `snapshot/manager.py`: Cached file loading (`_load_file_content_cached`, `_get_search_directories_cached`). New incremental sync mode that skips per-file copies when the destination already matches by size/mtime — safe for workdir→shadow direction only.

- **Feature: Read/LS/Glob/Grep auto-approved on skill and plugin directories**:
  - New `approve_if_path_inside_skill_or_plugin_dir` predicate that resolves all skill search directories (builtin, home, project, extras) via `SkillManager.get_search_directories()` and explicit `CFG.LLM_PLUGIN_DIRS` at call time — respects programmatic overrides.
  - Registered in `chat.py` for `Read`, `LS`, `Glob`, `Grep`, `AnalyzeFile`.

- **Feature: YOLO mode propagated to sub-agents**:
  - `yolo.py`: `make_yolo_inheritance_checker()` now handles `frozenset` (selective YOLO) — when the parent has selective YOLO enabled, only the named tools are auto-approved in sub-agents. Previously selective YOLO degraded to full YOLO in sub-agents.
  - `delegate.py`: Added `yolo` property to `BufferedUI` that delegates to the wrapped parent UI, so `check_yolo_inheritance`'s UI fallback works through the buffered wrapper.

- **Feature: Escape cancellation preserves conversation history**:
  - When pressing Escape to cancel an LLM response, the user's message and a `[SYSTEM: Response was interrupted by user]` marker are now saved to conversation history. The next turn builds on the interrupted context instead of starting fresh. No changes to `runner.py` — handled entirely in `_exec_action_inner` in `llm_task.py`.

- **Improvement: Project-context file reading cached**:
  - `claude.py`: `_load_file_content` now caches reads by `(path, mtime)` so per-turn AGENTS.md/CLAUDE.md re-reads cost only a stat call. `_get_search_directories` also cached per `(home, cwd)` pair.
  - Fixed `break` → `continue` in `create_project_context_prompt` — was skipping all doc files after README; now correctly continues to remaining files.

- **Improvement: File tool error handling**:
  - `file_read.py`, `file_edit.py`, `file_search.py`: Better path validation, fuzzy matching helpers (`_find_fuzzy_match`, `_match_line_trimmed`), indentation-flexible matching (`_match_indentation_flexible`).

- **Improvement: `assistant_name` check tightened**:
  - `manager.py`: `if assistant_name` → `if assistant_name is not None` so empty string `""` is no longer replaced by `CFG.LLM_ASSISTANT_NAME`.

- **Chore: Removed dead exports** — `tool/__init__.py` and `tool_call/__init__.py` cleaned up, unused `default_tools.py` tool removals.

## 2.27.1 (May 14, 2026)

- **Refactoring: Shared filesystem-scanning utilities extracted**:
  - New `src/zrb/util/asset_scanner.py` exposes `scan_files(directory, max_depth, on_file_found, ignore_dirs)` and a module-level `IGNORE_DIRS` constant (`.git`, `node_modules`, `__pycache__`, `venv`, `dist`, `build`, `htmlcov`). Replaces the duplicated `_scan_dir` / `_scan_dir_recursive` pattern that previously lived in both `llm/skill/manager.py` and `llm/agent/subagent/manager/loader_mixin.py`. Silently swallows `PermissionError`/`OSError` so one inaccessible branch never aborts a full scan.
  - New `src/zrb/util/dir_search.py` exposes `get_upward_dirs(start_dir)` (root → cwd traversal for multi-tier project-config discovery) and `scan_plugin_dirs(plugins_root)` (returns plugin dirs containing a `.claude-plugin/plugin.json` manifest). Shared by the skill loader and the hook loader so the "user home → project dirs → plugins → builtin" discovery order has one canonical implementation.
  - `llm/skill/manager.py` and `llm/agent/subagent/manager/loader_mixin.py` switched to `scan_files()` + `_on_file_found` callbacks; private `_IGNORE_DIRS` removed in favour of `asset_scanner.IGNORE_DIRS`.

- **Refactoring: `hook_loader.get_search_directories()` decomposed**:
  - One monolithic function split into `_get_plugin_hook_dirs`, `_get_home_hook_dirs`, `_get_project_hook_dirs`, `_get_custom_hook_dirs` + a shared `_collect_hook_paths(base_dir)` helper. Eliminates the repeated Claude-style/Zrb-style path-building blocks for each discovery tier.
  - New `_zrb_dir_name()` helper evaluates `f".{CFG.ROOT_GROUP_NAME}"` lazily to dodge CFG init-ordering issues.
  - Priority order now documented in the module docstring (high → low): plugins → user-home config → project dirs → `CFG.HOOKS_DIRS`.

- **Refactoring: `file_search` output assembly deduplicated**:
  - New helpers in `llm/tool/file_search.py`: `_build_file_match_entry`, `_count_actual_matches`, `_truncate_file_results`, `_build_search_output`. The ripgrep path and the `os.walk` fallback path now share final result-dict assembly (results / summary / truncation notice / warning), eliminating divergent code that had grown different no-match messaging and truncation behaviour.

- **Refactoring: `CLIStyleLexer` color tables hoisted**:
  - `llm/app/lexer.py`: `_STANDARD_FG` / `_BRIGHT_FG` color tables and the `_build_style(attrs, fg, bg)` composer promoted from nested closure to module-level constants. `lex_document` now declares its state as `attrs` / `fg` / `bg` (was `current_*`) for readability. Added a class docstring enumerating supported ANSI features (bold/faint/italic/underline; 8 std + 8 bright FG/BG; 24-bit RGB `38;2;R;G;B`; 256-color palette `38;5;N`; state persistence across lines).

- **Refactoring: Long-method decomposition across LLM internals**:
  - `llm/prompt/manager.py`, `llm/snapshot/manager.py`, `llm/task/chat/runner_mixin.py`, `llm/history_manager/file_history_manager.py`, `llm/hook/interface.py`, `llm/message.py`, `llm/tool/plan.py`, `llm/agent/subagent/manager/manager.py`, `llm/agent/subagent/manager/search_mixin.py`, and `task/base/monitoring.py` all received internal restructurings — extracting helpers from oversized methods, grouping related methods together, and tightening reorder for readability. No behavior changes.
  - `llm/skill/manager.py` lost its private `_ensure_scanned()` helper (inlined where called); `LoaderMixin._scan_dir_recursive` removed (delegated to `scan_files`).

- **Refactoring: `system_context.py` parallel git/todo collection extracted**:
  - New `_collect_git_info(todo_manager, session_name)` helper runs git commands and todo fetch in parallel via `ThreadPoolExecutor`. Lazy-imports `is_inside_git_dir` at call time (was a module-level import). Module gains a docstring documenting the three auto-injections it performs beyond environment facts (session wiring, active worktree, pending todos).

- **Improvement: Mandate (operating rules) tightened**:
  - `mandate.md` rewritten for concision: emphatic prose ("MUST", "non-negotiable") softened to direct statements; redundant explanations folded into single-line bullets; rule priority list condensed; `Engineering Standards` bullets merged (`Stay in scope`, `Avoid band-aids`, `Verification (path to finality)` consolidated into `Minimal abstractions` / `Trade-offs are explicit` / `Done = verified`). New `Recovery` section codifies the missed-skill-activation and 3-distinct-failures protocols. New "soft override" framing in rule #7 makes the precedence between project conventions (`AGENTS.md`/`CLAUDE.md`) and safety rules explicit.
  - `journal_mandate.md` condensed from ~50 lines to ~40 with the same protocol — write categories consolidated, scan/navigate guidance shortened, headings normalized to sentence case.
  - `core-coding/SKILL.md` adds one sentence directing the LLM to prefer user-provided guidelines (`CLAUDE.md`, `AGENTS.md`, custom skills, project files) over the core companion files; core companions "fill in the gaps."

- **Improvement: `AGENTS.md` deduplicated against `contextvars.py`**:
  - The inline "Ambient State" table listing every `ContextVar`, its owning module, and its wrapper was removed. `AGENTS.md` now points readers to `src/zrb/contextvars.py` as the single source of truth. Removes a synchronization point that had previously caused drift between the table and the actual code.
  - `contextvars.py` docstring updated: `AGENTS.md` no longer needs updating when the ContextVar list changes; `docs/advanced-topics/maintainer-guide.md` and `docs/advanced-topics/architecture.md` are now the only docs that mirror the count.
  - System Context section in `AGENTS.md` shortened — the long bullet list of auto-injections was moved into the `system_context.py` module docstring instead.
  - `session_state_log/` and `session_state_logger/` collapsed into one table row that explains the split (`_log` = data structures, `_logger` = persistent writer).
  - `llm/util/` row expanded to enumerate the helper modules (`attachment`, `clipboard`, `git`, `history_formatter`, `image_scale`, `modality`, `multimodal_describe`, `prompt`, `stream_response`).

- **Bug Fix: Typo `notify_throtling` → `notify_throttling`**:
  - `llm/agent/run/runner.py:_acquire_rate_limit`: inner closure name corrected. Pure rename — no behavior change.


## 2.27.0 (May 14, 2026)

- **Feature: New skill architecture — 5 core skills with companion files**:
  - Introduced 5 consolidated core skills (`core-coding`, `core-research`, `core-design`, `core-writing`, `core-journaling`) serving as methodology hubs with companion files (language guides, workflow guides, templates, tools).
  - `core-coding`: 7 language-specific companions (`python.md`, `go.md`, `java.md`, `php.md`, `ruby.md`, `rust.md`, `typescript.md`) with language conventions, idioms, and gotchas; 4 workflow companions (`testing.md`, `debug.md`, `refactor.md`, `review.md`) with detailed step-by-step methodologies.
  - `core-design`: Decision record template (`templates/decision-record.md`) for architecture decisions.
  - `core-writing`: 3 writing templates (`api-doc.md`, `commit-message.md`, `readme.md`) with AIDA/PAS/FEBC copywriting frameworks.
  - `core-journaling`: Activity log template (`templates/activity-entry.md`); journal lint tool (`tools/journal-lint.py`) for backlink validation and orphan detection.
  - `core-research`: Scope → Discover → Synthesize → Plan workflow with approval gate enforcement.

- **Feature: Skill activation table in mandate**:
  - New Skill Activation section in `mandate.md` with a domain-to-skill mapping table (Software Engineering → `core-coding`, Research → `core-research`, Design → `core-design`, Writing → `core-writing`).
  - Activation rules: auto-approved, silent, once per session per domain, skip for trivial lookups.
  - Skill override hierarchy documented: core-coding overrides Engineering Standards; core-research overrides "work autonomously" directive; core-design enforces no-implementation-during-design; core-writing overrides generic Task Handling.

- **Feature: Skill slash-commands refactored to thin delegation stubs**:
  - `/debug`, `/testing`, `/review`, `/refactor`, `/research` now delegate to the appropriate core-skill companion file instead of carrying complete workflows inline.
  - All user-invocable skills gained `disable-model-invocation: true` — only fire when the user explicitly calls the `/command`.
  - Old `research-and-plan` skill removed (replaced by `/research` + `core-research`).

- **Refactoring: Mandate (operating rules) rewritten for clarity and thoroughness**:
  - `mandate.md`: Sections reorganized — new Session Context, Tool Use, Communication sections added; Execution Loop, Engineering Discipline, Multi-Step Tasks folded into consolidated Task Handling and Engineering Standards. Rule priority elevated Quality (#3) and Skill Activation (#5); Scope moved to #6. Tiebreaker changed from "analysis > action" to "quality > shortcuts, evidence > assumptions." Added "Strategic re-evaluation" (stop after 3 failed attempts), "Verification (path to finality)" (tests + linter + type-checker + docs), and "Default to no comments" rules.
  - `persona.md`: Identity changed from "Lead Engineer" to "versatile engineer, researcher, and writer." Added "Plain text: no emojis" and "Quality bar" guidance. Response calibration now distinguishes depth by context type (lookups vs analysis vs structured docs).
  - `journal_mandate.md`: Expanded with two-write-kind system (Insight vs Activity), explicit "Always journal / Always log / Skip" categories, "How to Write" section mandating `core-journaling` activation before every write, and "How to Scan" protocol for significant turns.
  - `persona.md`: Removed redundant pre-tool-narration and post-task-summary rules (moved to Communication section in mandate).

- **Improvement: Tool guidance strings tightened**:
  - `chat.py`: All `_static_tool_guidance` entries rewritten for concision — removed redundant `when_to_use` values, shortened `key_rule` text, merged `LspFindDefinition` guidance into generic LSP guidance. Removed `SearchJournal` standalone guidance entry. Comment added: "File Operations — only non-obvious gotchas. Tool names say what they do."

- **Security: CVE-2026-45134 langsmith bump**:
  - `pyproject.toml`: langsmith pinned to `>=0.8.0` (was `>=0.7.31`) for GHSA-3644-q5cj-c5c7 — public prompt pull deserializes untrusted manifests enabling SSRF / prompt injection via attacker-controlled prompt manifests.
  - `journal-lint.py` hardened against path traversal / shell injection in the security-fix commit.

- **Bug Fix: Worktree staleness guard**:
  - `system_context.py`: If `active_wt` path no longer exists on disk, the stale worktree is cleared from ambient state (imported `set_active_worktree`). Prevents displaying a deleted worktree path in the system context.
  - Test fix: `test_worktree.py` creates the mock worktree directory with `os.makedirs` before the system context assertion.

- **Improvement: RTK.md included in project context**:
  - `claude.py`: Added `RTK.md` to the project context search filenames list, so RTK configuration is auto-included when present.

- **Test Infrastructure**: 1621 tests pass across the LLM test suite.

- **Bug Fix: `CustomCommand` dollar-sign guard suppressed args for prompts with literal `$`**:
  - `custom_command.py` removed the `"$" not in self._prompt` guard that prevented argument appending when the prompt contained any dollar sign (regex patterns, shell examples, prices) without actual placeholder variables. Skills like `Match end of line: \d+$` now correctly pass `ARGUMENTS` through.
  - Test: `test_get_prompt_literal_dollar_not_placeholder` in `test_custom_command.py`.

- **Refactoring: Shared companion-file utilities extracted**:
  - New `src/zrb/llm/skill/_util.py` holds `discover_companion_files()` (recursive `rglob`, excludes `SKILL.md`/`SKILL.py` itself) and `format_companion_file_lines()` (groups files by top-level directory). Shared across `tool/skill.py`, `skill_command_factory.py`, and `manager.py`.
  - `tool/skill.py`: Private `_get_companion_files()` replaced with the shared `discover_companion_files()` from `_util.py`.

- **Improvement: Skill activation headers clarified**:
  - `ActivateSkill` tool output (`tool/skill.py`) now shows a consistent header with "Skill activated. The following context applies:" preamble, the skill directory marked as "working directory", a note that "All file paths ... are relative to this directory.", and grouped companion file listing (previously flat `-` bullet list).
  - `SkillCommandFactory` (`skill_command_factory.py`) now prepends the same companion-file context header to skill slash-command prompts, matching the `ActivateSkill` tool behavior.
  - Companion file formatting moved from `skill.py`'s inline `- {name}` to `format_companion_file_lines()` with directory grouping (e.g. `scripts/` → `setup.sh`, `run.sh`).

- **Documentation: "Companion Files" section added**:
  - `docs/advanced-topics/claude-compatibility.md` documents the `SKILL.md`/`SKILL.py` directory convention, companion-file auto-discovery, and example directory structure. Linked from the `ActivateSkill` tool description in the skill authoring guide.

- **Test Infrastructure: `Skill` mock attribute coverage**:
  - `companion_files` attribute added to `Skill` mocks in `test_skill.py` (2 tests) and `test_skill_command_factory.py` (3 tests) to match the new `Skill` class interface.
  - New `test/llm/skill/test__util.py`: 8 tests covering `discover_companion_files` (flat file, SKILL.md, SKILL.py, missing directory) and `format_companion_file_lines` (empty, standalone, grouped, mixed).


## 2.26.8 (May 13, 2026)

- **Bug Fix: `SnapshotManager` skips large regenerable directories**:
  - New `DEFAULT_IGNORE_DIRS` frozenset (`src/zrb/llm/snapshot/manager.py:44`) covers Python (`.venv`, `venv`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.tox`, `.eggs`), Node/JS (`node_modules`, `.next`, `.nuxt`, `.turbo`, `.parcel-cache`), and generic caches (`.cache`). Skipping them reduces backup/restore from multi-second to sub-second on large projects.
  - `_sync_dirs()` gains an `ignore_dirs` parameter; the `_prune()` helper is applied symmetrically in both `os.walk` passes (copy and delete). Empty-directory cleanup also respects ignored paths.
  - `SnapshotManager.__init__()` accepts optional `ignore_dirs` (defaults to `DEFAULT_IGNORE_DIRS`). All three call sites (`backup`, `restore`, `init`) pass `self._ignore_dirs` through.

- **Bug Fix: `ZRB_LLM_PLUGIN_DIRS` tilde expansion**:
  - `LLMSearchMixin.LLM_PLUGIN_DIRS` (`src/zrb/config/mixins/llm_search.py:35`) now passes each path through `os.path.expanduser()` so values like `~/.bsim-ai-workflow` resolve to the absolute home path. Previously `~` was treated as a literal directory name.
  - Test: `test_llm_plugin_dirs_tilde_expansion` added in `test/config/test_config.py`.

- **Refactoring: `OutputMixin` exposes `is_thinking`/`current_confirmation` as properties**:
  - `OutputMixin` (`src/zrb/llm/ui/default/output_mixin.py`) now defines `is_thinking` and `current_confirmation` as proper `@property` pairs with getters and setters. All internal access and test code (`test_output_mixin.py`) updated to use the public property names instead of private `_is_thinking`/`_current_confirmation`.

- **Documentation: Updated stale version references and task-subclass docs**:
  - `docs/installation/installation.md` and `docs/advanced-topics/ci-cd.md`: Docker image tags and version references updated from `2.0.0` to `2.26.8`.
  - `docs/core-concepts/tasks-and-lifecycle.md` and `docs/task-types/custom-tasks.md`: All code examples updated from `Task`/`run()`/`async_run()` to `BaseTask`/`_exec_action()`. Added warning against overriding `run()` directly. Added `Retry Behavior` section. Removed separate "Async Tasks" heading.

- **Test Infrastructure: Test files relocated**:
  - `test/util/llm/*` → `test/llm/util/*` (7 files relocated — `test_attachment.py`, `test_clipboard.py`, `test_image_scale.py`, `test_modality.py`, `test_multimodal_describe.py`, `test_prompt.py`, `test_prompt_util.py`).


## 2.26.7 (May 12, 2026)

- **Security: Removed `mistralai` optional dependency**:
  - `mistralai` package was quarantined on PyPI (pydantic-ai [#5382](https://github.com/pydantic/pydantic-ai/issues/5382), [#5384](https://github.com/pydantic/pydantic-ai/pull/5384)). The optional dependency declaration in `pyproject.toml:79` is now commented out to prevent installation failures.
  - `"mistral"` removed from the `all` extras list (`pyproject.toml:158`) — was a dangling reference to the now-commented `mistral` extras group.
  - `poetry.lock` regenerated; `mistralai` v2.2.0 and its transitive deps (`eval-type-backport`, `jsonpath-python`) purged from the lockfile.
  - No source-level imports of `mistralai` exist in the codebase — clean removal with no breaking changes.


## 2.25.0 (May 12, 2026)

- **Improvement: Assistant Name Auto-Capitalization**:
  - `LLM_ASSISTANT_NAME` first letter is now automatically capitalized in `llm_ui_styles.py`, `prompt.py`, `base/ui.py`, and `std_ui.py`. Preserves existing casing on the remainder (e.g. `"zrb"` → `"Zrb"`, `"customAssistant"` → `"CustomAssistant"`).
  - `get_persona_prompt()` in `prompt.py` now also capitalizes the `{ASSISTANT_NAME}` placeholder.
  - `BaseUI.__init__` in `base/ui.py`: falls back to `CFG.LLM_ASSISTANT_NAME` when `assistant_name` is empty/`None` (was left as `""`, which could produce empty assistant labels).
  - `StdUI` now accepts a new `assistant_name` constructor parameter and uses the configured name instead of the hardcoded `"Zrb"` for the confirmation waiting indicator message.

- **Bug Fix: Opaque 400 Retry Skipped During Tool-Call Iterations**:
  - `retry_loop.py`: Removed the `current_message is not None` guard from the generic opaque-400 handler. During tool-call iterations and outer-retry resume, `_merge_consecutive_messages` merges the user message into a previous `ModelRequest`, making `current_message` `None`. Previously this skipped the text-only fallback entirely. Now injects a `[SYSTEM]` fallback prompt into the sanitized history when no message is pending, prompting a plain-text continuation instead of re-entering the tool-calling flow that triggered the rejection.
  - Test: `test_handle_stream_error_opaque_400_skipped_when_no_message` renamed to `test_handle_stream_error_opaque_400_with_no_message`; now asserts `should_retry is True` and verifies the injected fallback prompt.

- **Improvement: `strip_to_text_only` Converts `ThinkingPart`**:
  - `history_utils.py`: `strip_to_text_only` now also converts `ThinkingPart` → `TextPart` with its text content preserved (new `_thinking_part_content` helper). Previously thinking parts were left intact for the `is_missing_reasoning_content_error` handler, but if that handler already fired (or was inapplicable), the opaque-400 text-only fallback could still fail on reasoning content. Now the text-only fallback is truly text-only.
  - Test: `test_strip_to_text_only_converts_tool_parts_keeps_thinking` renamed to `test_strip_to_text_only_converts_all_non_text_parts`; now asserts `ThinkingPart` is converted to `TextPart`.


## 2.26.4 (May 12, 2026)

- **Bug Fix: `create_agent` uses `tool_retries` (was `retries`)**:
  - pydantic-ai renamed the `Agent` constructor parameter from `retries` to `tool_retries`. `common.py:202` updated to match — this was silently ignored; tool retries fell back to the default (1) regardless of configuration.
  - Test assertion in `test_common.py` updated to check `tool_retries` instead of `retries`.

- **Bug Fix: `is_invalid_tool_call_error` false-positives from wrapper metadata**:
  - New `_get_body_message()` in `error_classifier.py` extracts the provider's error message from `e.body` dict (not `str(e)`). The `str(e)` path was matching against wrapper metadata like `{'type': 'invalid_request_error'}` — the string `"request_error"` does not contain entity words but the dict's value or JSON representation could trigger spurious entity-keyword matches. Using the body's `message` field directly eliminates the false-positive surface.
  - All existing entity + problem keyword matching logic is preserved.

- **Bug Fix: `strip_to_text_only` converts tool parts to descriptive text**:
   - `ToolCallPart` → `TextPart("[Tool: <name>(<args>)]")`, `BaseToolReturnPart` → `TextPart("[Result (<name>): <content>]")` (was `UserPromptPart`). Both `ModelRequest` and `ModelResponse` accept `TextPart`, so the part type no longer changes with the container. Descriptive text preserves semantic context without provider-specific struct requirements.
   - `ThinkingPart` is now preserved — `is_missing_reasoning_content_error` in `retry_loop` handles the DeepSeek-style `reasoning_content` rejection upstream, so the opaque-400 fallback can safely keep all information.
   - Large tool results truncated to 500 chars to prevent context-window overflow during last-resort retry.
   - Empty `ToolCallPart` (no `tool_name`) now labelled as `[Tool: (unnamed)(<args>)]` instead of being dropped.
   - Nil/empty content in non-tool parts still normalised to `"."`.
   - Internal refactor: helpers extracted (`_tool_call_to_text`, `_tool_return_to_text`); `_normalize_content` no longer returns `None`, removing the downstream `None`-filter pass; redundant `has_tool` fallback branch simplified away.

- **Bug Fix: Stream context manager (resource leak fix)**:
  - `runner.py`: Changed from manual `stream = agent.run_stream_events(...)` + `finally: await stream.aclose()` to `async with agent.run_stream_events(...) as stream:`. The manual pattern held a reference across the event loop; if `aclose()` wasn't reached (e.g. during cancellation), the stream was leaked. The context manager guarantees cleanup.
  - Removed stale `stream = None` initialiser.

- **Test Infrastructure: `_stream_from` helper for async-with mocks**:
  - `test_runner.py`: All 14 `mock_run_stream_events` async generators replaced with `_stream_from()` that wraps the generator in `AgentEventStream`, matching the new context-manager interface. Two `side_effect=` assignments in `patch.object` calls (session_start and user_prompt tests) fixed — the old pattern assigned the generator directly to `side_effect` but `patch.object` creates a new mock, so the `side_effect` was set on the mock rather than on the original. Now `mock_run.side_effect = _stream_from(_gen)` sets it correctly on the mock returned by the context manager.


## 2.26.3 (May 11, 2026)

- **Bug Fix: Generic Opaque-400 Retry for Multi-Turn Format Rejection**:
  - New `strip_to_text_only()` in `src/zrb/llm/agent/run/history_utils.py` — normalises all message content to non-null, non-empty text strings; strips `ThinkingPart` (source of `reasoning_content` serialisation issues); preserves `ToolCallPart`, `ToolReturnPart`, `UserPromptPart`, and `TextPart` structure intact.
  - New `opaque_retry_done` flag in `RetryState` — fires a single retry for any unclassified HTTP 400 by collapsing history through `strip_to_text_only()`. Provider-agnostic: works for GLM-5 on Bedrock, local models, future providers — no per-provider error-string matching.
  - New `is_opaque_validation_error()` in `error_classifier.py` — documents the empty-`ValidationException` pattern (GLM-5 on Bedrock) for logging/metrics without coupling the retry loop to any specific provider.
  - The existing `is_missing_reasoning_content_error` + `strip_thinking_parts` path (DeepSeek) is preserved unchanged. The opaque handler sits last in the retry chain, so it only fires when all other handlers have given up.

- **New Tests**: 10 new test cases covering `strip_to_text_only` (structure preservation, null normalisation, empty guard, multi-turn flow, empty tool-call drop), opaque retry (fires once, skipped on second call, gated on `current_message`, gated on status 400), and `is_opaque_validation_error` (GLM-5 match, non-opaque ValidationException, DeepSeek non-match).

- **UI: Status Bar Styling Refactored to Inline CFG Styles**:
  - `get_status_bar_text()` now returns inline style strings from `CFG.LLM_UI_STYLE_STATUS`/`THINKING`/`CONFIRMATION` instead of CSS class names (`class:status`, etc.). Bypasses prompt_toolkit CSS class resolution — the style string goes directly to `_parse_style_str`.
  - `DEFAULT_LLM_UI_STYLE_BOTTOM_TOOLBAR` set to `"noinherit"` so the toolbar has no background/foreground/bold of its own. Only the fragment's ANSI color applies to the text glyphs.
  - Defaults: STATUS=`ansiwhite`, THINKING=`ansigreen`, CONFIRMATION=`ansiyellow`. All pure ANSI SGR codes (97/32/33) — no hex, no 24-bit, compatible with all terminals including tmux.

- **UI: Assistant Name Capitalized**:
  - `DEFAULT_LLM_ASSISTANT_NAME` changed from `""` (falls back to `ROOT_GROUP_NAME` → `"zrb"`) to `"Zrb"`. The name now shows as "Zrb" in the status bar and persona prompt.

- **UI: Smoother Status Bar Animations**:
  - `_refresh_loop` thinking sleep reduced from 0.5s → 0.25s for smoother dot animation.
  - Confirmation state now also triggers fast-poll (0.25s) when `_current_confirmation is not None`, matching the thinking pattern.

- **Security: urllib3 pinned to `>=2.7.0` (CVE-2026-44432)**:
  - urllib3 is a transitive dependency via requests and boto3. The vulnerability allowed cookie leakage on HTTPS → HTTP redirect. Pin added in pyproject.toml with advisory comment.


## 2.26.2 (May 11, 2026)

- **Performance: Debounced UI Invalidation**:
  - New `_schedule_invalidate()` in `OutputMixin` coalesces rapid `append_to_output` calls (e.g. streaming tool results) into a single invalidation per ~16ms frame. Previously every chunk triggered an immediate `invalidate_ui()` call.
  - Benchmarked reduction: **33–100× fewer** `invalidate_ui()` calls depending on streaming pattern — 100 rapid calls coalesce into 1; realistic bursts of 20 with 10ms gaps coalesce into 3.
  - `RuntimeError` fallback: when called outside an async context, `_schedule_invalidate()` catches the error and falls back to synchronous `invalidate_ui()` — no crash, no behaviour change.
  - `OutputMixin._schedule_invalidate()` and `UI._schedule_invalidate()` both carry the same debounce logic (via MRO precedence).

- **Improvement: Animated Thinking Indicator**:
  - Status bar now shows an animated dots sequence (`⏳ Zrb is working.` → `⏳ Zrb is working..` → `⏳ Zrb is working...`) instead of a static `⏳ ... is working...`.
  - Driven by `_thinking_dots` counter in `get_status_bar_text()`, advanced on every render call.

- **Improvement: Adaptive UI Refresh Loop**:
  - `LifecycleMixin._refresh_loop()` interval reduced from fixed 5.0s to 3.0s (idle) / 0.5s (thinking), enabling smooth dot animation without wasting CPU when idle.

## 2.26.1 (May 10, 2026)

- **Improvement: Prompt & Mandate Refinements**:
  - **Rule priority hierarchy** added (new rule #5): `AGENTS.md`/`CLAUDE.md` override on style/conventions; base operating rules override on safety. Resolves ambiguity between project-specific docs and the general mandate.
  - **"New code vs existing code" split**: previously the mandate said "prefer idiomatic code over existing style" (aggressive — would override local conventions). Now: idiomatic patterns for new code; match local style for existing code.
  - **Cross-reference to git rules** added in general mandate so the "Git Rules" section isn't discoverable only from `git_mandate.md`.
  - **Testing rules consolidated**: three separate bullets (Tests Are Integral, Testing Standards, Test File Conventions) merged into one dense bullet. Zero content loss.
  - **Removed redundant sections**: "Context & Token Efficiency" (covered by persona's Response Calibration), "activate core-coding skill first" (a tool-time decision), "Review Your Own Code" (implicit in Engineering Discipline).
  - `persona.md`: "One sentence before tools" → **"Pre-tool narration"**; "Reference code" → **"Cite code"** — clearer naming.
  - `git_mandate.md`: Diff threshold relaxed from `~100 lines` to **"too large to be useful inline"** with added **offer-to-share specific files** behavior.
  - `chat.py`: Tool guidance for `SearchJournal` and `SearchInternet` deduplicated — removed return-type schemas and config details that are already in the tool's own pydantic docstrings.

- **Improvement: Tool Docstring Clarity**:
  - `search_journal()`: "text pattern" → "regex pattern across all journal files in the configured journal directory" — more precise about scope and pattern type.

## 2.26.0 (May 10, 2026)

- **Feature: Multimodal Attachment Pipeline**:
  - New `LLM_MULTIMODAL_MODEL` env var / `LLMConfig.multimodal_model` property for designating a vision-capable model used to describe attachments when the main model is text-only.
  - New `LLM_MAX_IMAGE_DIMENSION` (default `1568`, Anthropic no-extra-cost tier) and `LLM_IMAGE_JPEG_QUALITY` (default `85`) knobs control image scaling.
  - Pasted (`Alt+V` / `Ctrl+V`) and `/attach`-ed images are auto-scaled to the cap on the longest edge before being added to the prompt; opaque images re-encode to JPEG, alpha-bearing images stay PNG.
  - Before each agent run, `runner._apply_multimodal_fallback` walks the prompt content: if the main model can't consume an image/audio attachment, the multimodal model describes it and the description text replaces the binary; if no multimodal model is configured, the attachment is dropped with a `⚠️ Dropped <modality> attachment` warning rather than silently sent to a provider that will reject or ignore it.
  - New utilities at `src/zrb/llm/util/`: `image_scale.py` (Pillow-backed downscale), `modality.py` (per-provider name-pattern detection of image/audio/video support), `multimodal_describe.py` (one-shot describe sub-agent + substitution helper).
  - Audio attachments via `/attach` get the same describe/transcribe fallback. Video attachments are kept as-is for Gemini-class models, dropped with a warning otherwise (auto frame-extraction is out of scope).

- **Performance: Defer default UI import in `zrb.llm.ui`**:
  - Moved `from zrb.llm.ui.default.ui import UI as _UI` from module top into the existing `__getattr__` so `prompt_toolkit` no longer loads on every `import zrb`.
  - Cuts ~25ms (~20%) off cold-import on a dev box; larger on slower machines (~250ms on a phone via Termux).
  - No public API change — `from zrb.llm.ui import UI` still works; the resolution is just lazy.

- **Dependency: bump `pydantic-ai-slim` to `~1.93.0`** (was `~1.90.0`).

- **Security: Bump `langchain-core` for CVE-2026-44843 (GHSA-pjwx-r37v-7724)**:
  - Pin raised from `>=1.2.28` to `>=1.3.3` (still in the `voyageai` extra).
  - LangChain's deserialization path used overly broad object allowlists, allowing prompt injection / credential disclosure via attacker-controlled structured input. CVSS 8.2.

- **Security: Correct `python-multipart` advisory description (GHSA-pp6c-gr5w-3c5g)**:
  - Pin unchanged at `>=0.0.27`. Comment updated — the actual issue is unbounded multipart **header count and size** causing CPU exhaustion, not the previously-described preamble/epilogue handling.

- **Tests**: 100% coverage for `src/zrb/llm/util/clipboard.py` (was 17%) and full coverage for the three new multimodal modules.


## 2.25.3 (May 8, 2026)

- **Bug Fix: `filter_nil_content` Crashed on `BuiltinToolCallPart`**:
  - `_sanitize()` in `src/zrb/llm/agent/run/history_utils.py` called `dataclasses.replace(part, content=...)` on dataclass parts that have no `content` field (e.g. `BuiltinToolCallPart`, used for provider-side tools like Anthropic web_search). The `getattr(part, "content", None)` returned `None`, the code thought the content was nil, and `replace()` raised `TypeError: __init__() got an unexpected keyword argument 'content'`. Hit on every model call when builtin tools were enabled.
  - Fixed by gating the replace on `hasattr(part, "content")` before treating missing content as nil.
  - Refined the placeholder check to use `BaseToolReturnPart` (parent class) so `BuiltinToolReturnPart` also gets `"null"` instead of `"."` when its content is nil.
  - New regression tests: `test_filter_nil_content_preserves_builtin_tool_call_part` and `test_filter_nil_content_uses_null_for_builtin_tool_return`.

- **Bug Fix: GLM-5 / Bedrock `ValidationException` Detection**:
  - `is_missing_reasoning_content_error()` in `src/zrb/llm/agent/run/error_classifier.py` now also matches Bedrock `ValidationException` responses with an empty `Error.Message` field — the pattern produced by GLM-5 on Bedrock when it rejects `ThinkingPart` entries in echoed history. Previously these slipped through and surfaced as opaque 400s; now they trigger the existing `strip_thinking_parts` retry path.

- **Bug Fix: Self-Import in `attachment.py`**:
  - `normalize_attachments()` in `src/zrb/llm/util/attachment.py` had `from zrb.llm.util.attachment import get_media_type` — a self-import working around the function being defined later in the same file. Removed; `get_media_type` is in scope at call time.

- **Bug Fix: Dead `mock.patch` Sites in Hook Tests**:
  - Six tests across `test/llm/hook/{test_matchers,test_hook_result_processing}.py` and `test/llm/hook/manager/test_hook_manager.py` patched `zrb.llm.hook.manager.manager.CFG` even though `manager.py` never read `CFG`. The patches were no-ops — the tests passed only because the *other* patch in the same `with` block (`zrb.llm.hook.journal.CFG`) did the real work. Removed the dead patches and the corresponding dead `mock_mgr_cfg.*` attribute assignments.

- **Refactoring: Sub-Agent Manager Nested Layout**:
  - `src/zrb/llm/agent/subagent/{manager,loader_mixin,search_mixin}.py` moved to `src/zrb/llm/agent/subagent/manager/` to match the `hook/manager/` and `lsp/manager/` layouts. `subagent/manager/__init__.py` re-exports `SubAgentManager`, `SubAgentDefinition`, and `sub_agent_manager` so external imports continue to work.
  - `src/zrb/llm/tool/delegate.py` now imports directly from `zrb.llm.agent.subagent.manager.manager` (the inner module) to avoid a circular import: the package `__init__.py` triggers `register_default_tools()` mid-load, which transitively pulls `tool/delegate.py` before `__init__.py` has finished re-exporting `SubAgentManager`.
  - Six `unittest.mock.patch("zrb.llm.agent.subagent.manager.create_agent")` sites updated to `...manager.manager.create_agent` (where `create_agent` actually lives post-migration).

- **Refactoring: Typed Mixin Contracts**:
  - All eight mixin pairs in scope now declare host-class attributes via `if TYPE_CHECKING:` annotation blocks. Static type checkers see the required interface; runtime sees nothing (zero attribute leaks confirmed by `dir()`). Renaming a host attribute now produces a static type error in every mixin that reads it.
  - Updated: `agent/subagent/manager/{loader_mixin,search_mixin}.py`, `lsp/manager/lifecycle_mixin.py`, `ui/default/{confirmation,output,keybindings,lifecycle}_mixin.py`, `ui/base/commands_mixin.py`, `hook/manager/loader_mixin.py`. The previously docstring-only contracts in `commands_mixin.py` and `hook/manager/loader_mixin.py` were converted to typed annotations and the now-redundant docstring lists removed.

- **Refactoring: Lazy-Import Sweep + Documented Policy**:
  - All 60 stdlib in-function imports (uuid, json, re, os, dataclasses, traceback, base64, pathlib, etc.) hoisted to module top across 30 files — stdlib is fast and rarely participates in zrb's circular graphs.
  - 30 internal `zrb.*` in-function imports hoisted where safe (verified by per-file `python -c "import <module>"` smoke check).
  - 13 internal in-function imports kept lazy with explicit `# lazy: <reason>` comments — categorized as: (a) circular avoidance, (b) transitively heavy via internal (e.g. `zrb.llm.agent` pulls `pydantic_ai`), or (c) test patch seam (tests patch the source path; hoisting binds the name at consumer-load and bypasses the mock).
  - New `Imports` section in `AGENTS.md` documents the four lazy-import categories and the `# lazy:` tagging convention.

- **Improvement: Dead Code Removal + Lint Enforcement**:
  - `flake8 src/zrb --select=F` now runs as part of `./zrb-test.sh` (gated before pytest). Catches unused imports, redefinitions, and undefined names; respects `# noqa: F401` on intentional re-exports.
  - Removed `zrb.util.callable.get_callable_name` and `zrb.util.truncate.truncate_str` (tested but never called from production code) plus their test files.
  - Eight unused imports removed across `llm/app/keybinding.py`, `llm/ui/simple_ui_base.py`, `llm/util/stream_response.py`, `runner/chat/chat_session_manager.py`, `runner/web_route/login_page/login_page_route.py`, etc.

- **Improvement: PyPI README Single-Source**:
  - `README.md` is now the single source of truth and uses **relative** `docs/X` links (works locally and on GitHub).
  - New `scripts/build_pypi_readme.py` rewrites those relative links to absolute, **version-tagged** GitHub URLs and writes `README.pypi.md` (the file Poetry packages, configured via `[tool.poetry] readme = "README.pypi.md"`).
  - The `publish-zrb-to-pip` task in `zrb_init.py` runs the script before `poetry publish`, so each PyPI release links to the matching version's docs (e.g. v2.25.3 links to `/blob/v2.25.3/...`) — old release pages stay correct even when files reorganise on `main`.

- **Improvement: Module Docstrings on Heavy Files**:
  - Six high-traffic files now lead with a short docstring describing what the module owns, who its key collaborators are, and a doc pointer for the *why*: `llm/agent/run/{runner,history_utils,openai_patch}.py`, `llm/task/chat/task.py`, `llm/ui/base/ui.py`, `llm/hook/manager/manager.py`.

- **Documentation: New LLM Chat Lifecycle Tour**:
  - `docs/advanced-topics/llm-chat-lifecycle.md` — a single-page narrative walking `zrb llm chat "..."` through every stage from CLI bootstrap to history persistence, with file paths at each step. Linked from the README doc index, AGENTS.md, and the Maintainer Guide TOC.

- **Documentation: ContextVar Count Reconciled**:
  - The codebase has **seven** `ContextVar` instances; `architecture.md` and `maintainer-guide.md` previously said "five." Both updated. `maintainer-guide.md` now documents three layers (task / agent / tool) instead of two, with a new table for `active_worktree` and `_current_session`.
  - Added a maintenance note in `src/zrb/contextvars.py`'s docstring listing the three docs that must be updated when the list changes, to prevent future drift.

## 2.25.2 (May 6, 2026)

- **Feature: Google News RSS as Default Search Backend**:
  - New `src/zrb/llm/tool/search/google_rss.py` implements `SearchInternet` via the Google News RSS feed (`https://news.google.com/rss/search`). Free, no API key, no Docker required.
  - `web.py`: SearXNG is now only invoked when `ZRB_SEARCH_INTERNET_METHOD=searxng` is explicitly set. Google News RSS is the new default fallback when no other method matches.
  - Added `_normalize_google_rss()` normalizer and wired it into `normalize_search_result()`.
  - `InternetSearchMixin`: `DEFAULT_SEARCH_INTERNET_METHOD` changed from `serpapi` to `google_rss`.
  - `docs/configuration/llm-config.md`: Added "Google News RSS (Default)" section; updated `ZRB_SEARCH_INTERNET_METHOD` options and default.
  - `docs/advanced-topics/llm-integration.md`: Updated `SearchInternet` tool description to reflect zero-setup default.

- **Fix: SearXNG Docker Setup**:
  - `start.py`: Config is now copied to `~/.config/searxng/settings.yml` (was incorrectly placed at `~/.config/searxng/settings.yml.new`). Docker volume mount corrected from `./config/` to `./.config/searxng/`. `SEARXNG_LIMITER=false` passed as env var to suppress limiter startup noise. Docker image pinned to `docker.io/searxng/searxng:2026.5.6-36bcd6b55` (fixes Wikidata `KeyError: 'name'` present in older versions). Secret key is now generated with `secrets.token_hex(32)` at copy time instead of using the hardcoded `"ultrasecretkey"` default (which causes SearXNG to refuse to start).
  - New `config/limiter.toml`: Copied alongside `settings.yml` to silence the "missing limiter config" warning at startup.
  - `config/settings.yml.new`: Replaced with the canonical `settings.yml` extracted directly from the pinned Docker image. Changes from the upstream default: added `json` to `formats` (required for the JSON API); removed `ahmia` and `torch` engine entries entirely (both require Tor and cannot be safely disabled via `disabled: true`); added `base_url: [https://yacy.searchlab.eu]` to the `yacy images` entry.

- **Performance: System Context Caching**:
  - `system_context.py`: Project type detection, infrastructure detection, marker scanning, and tool availability (`which()`) are now `@lru_cache`d per-CWD. These were previously recomputed on every turn despite being stable for the lifetime of a session.
  - ThreadPoolExecutor reduced from 16 workers to 4 — only git status/log and todo fetching remain dynamic.
  - `git.py`: `is_inside_git_dir()` now wraps an `@lru_cache`d `_check_git_dir(cwd)` to avoid repeated `git rev-parse` subprocess calls.

- **Performance: Prompt Loading Caching**:
  - `prompt.py`: `_find_custom_prompt()`, `_get_default_prompt_search_path()`, and `_read_package_prompt()` are now `@lru_cache`d. Prompt file search paths and bundled markdown files are computed once per CWD/name combination.
  - `_get_prompt_replacements()` now keyed by journal index file mtime — only recomputes when the journal actually changes (previously rebuilt on every turn).

- **Performance: LLMTask System Prompt Deduplication**:
  - `llm_task.py`: `get_system_prompt()` now called once and reused for both `_create_agent()` and `run_agent()`, avoiding rebuilding the prompt (including expensive system context I/O) a second time per turn.

- **Improvement: UI Confirmation Waiting Indicator**:
  - Status bar now shows a waiting-for-confirmation indicator (`👋 <name> is waiting for confirmation`) when a tool confirmation is pending, using new `LLM_UI_STYLE_CONFIRMATION` style (default: `ansiyellow bold`).
  - `StdUI`: Shows "👋 Zrb is waiting for confirmation" on stderr when no explicit prompt is given for tool-confirmation requests.
  - `ConfirmationMixin`: `get_app().invalidate()` now called unconditionally (not just when prompt text is non-empty) so the status bar reflects state transitions back to "working" or "ready" when the confirmation queue empties.

## 2.25.1 (May 6, 2026)

- **Bug Fix: Typo in `llm_task.py`**:
  - Fixed `default_llm_limitter` → `default_llm_limiter` (triple `t` → double `t` in variable name) in import alias and all references (`self._llm_limitter` → `self._llm_limiter`, property accessor).

- **Improvement: Journal Reminder Decoupled from Master Switch**:
  - `ZRB_LLM_INCLUDE_JOURNAL_REMINDER` now defaults to `off` independently, instead of falling back to `ZRB_LLM_INCLUDE_JOURNAL` (which defaults to `on`). Setting `ZRB_LLM_INCLUDE_JOURNAL=off` still disables the reminder as a guard.
  - `LLMPromptMixin` in `llm_prompt.py`: Added `DEFAULT_LLM_INCLUDE_JOURNAL_REMINDER: str = "off"`; updated `LLM_INCLUDE_JOURNAL_REMINDER` property to use `get_env()` with the independent default and a master-switch guard.
  - `llm-config.md`: Updated config table defaults from `1`/`0` to `on`/`off` for all prompt flags; documented `ZRB_LLM_INCLUDE_JOURNAL_REMINDER` as default `off` with conditional on master switch.

- **Improvement: Journal Mandate Expanded, Reminder Slimmed**:
  - `journal_mandate.md`: Added "Journal autonomously — do not wait for reminders" directive at the top of the When to Write section. Added "How to scan for journal-worthy content" subsection with step-by-step instructions (scan from last journal write, use `SearchJournal` to deduplicate, activate `core-journaling` skill for structural guidance).
  - `journal_reminder.md`: Replaced the detailed multi-line reminder with a single lightweight `[SYSTEM REMINDER]` nudge. The detailed what/how guidance now lives exclusively in the journal mandate (which is always in the system prompt), making the reminder a minimal prompt to act.
  - `journal.py`: Updated `_build_reminder()` docstring to reflect the lightweight-nudge role.

## 2.25.0 (May 5, 2026)

- **Improvement: Comprehensive History Sanitization Layer**:
  - New `sanitize_history()` in `history_utils.py` is a 4-stage pipeline (filter nil content → strip orphaned tool calls → drop empty messages → ensure alternating roles) that replaces the single `filter_nil_content()` call in the execution loop.
  - New `_detect_problems()` logs invariant violations at DEBUG level before sanitization runs, enabling root-cause tracing of provider 400 errors.
  - New `sanitize_orphaned_tool_calls()` in `message.py` removes unmatched `ToolCallPart`/`ToolReturnPart` pairs that can appear after history compression.
  - New `strip_thinking_parts()` strips `ThinkingPart` from responses for providers (e.g., DeepSeek) that reject `reasoning_content` in multi-turn histories.
  - New `is_missing_reasoning_content_error()` in `error_classifier.py` detects DeepSeek V3.2/V4 errors where the provider requires `reasoning_content` in history — triggers a one-time retry with `strip_thinking_parts`.
  - `is_invalid_tool_call_error()` now requires BOTH an entity word ("tool"/"function") AND a problem word ("unknown"/"invalid"/etc.) to avoid false positives on generic HTTP 400 errors.
  - `filter_nil_content()` now catches empty strings (`if not part.content` instead of `if part.content is None`) and handles thinking-only responses by injecting a `TextPart(".")` placeholder.
  - `runner.py`: The execution loop now calls `sanitize_history()` instead of `filter_nil_content()`, with `allow_orphaned_tool_calls=True` when deferred tool results are pending.
  - `runner.py`: Removed unnecessary `await asyncio.sleep(0)` from the streaming event loop.
  - Documented in `docs/advanced-topics/maintainer-guide.md` under a new "LLM History Sanitization Layer" section.

- **Improvement: Prompt & Mandate Overhaul**:
  - `persona.md`: "State intent before tool calls" → "State what you're about to do, then call"; added "Skip pre-tool narration for single-tool calls" and "skip post-task summary when there's nothing to report."
  - `mandate.md`: Changed priority tiebreaker from `action > analysis` to `analysis > action`; removed "Git state changes" from confirm-before table (moved to git_mandate.md); renamed "Edge Cases" → "Engineering Discipline" with Scientific Method, Atomic Changes, No Magic, Defensive Not Paranoid, Review Your Own Code; replaced "No Hacks" with "Avoid band-aids" (acknowledging suppression annotations are sometimes necessary); added "Modularity" and "Comments" rules; added "Prefer idiomatic code over existing style," "Minimal Changes," "Understand First" to Scope & Simplicity; consolidated token efficiency rules into two bullets (Be concise, Prioritize recent context); expanded Execution Loop with Root Cause First, Tests Are Integral (TDD), Testing Standards (≥80%, AAA, no private members), Test File Conventions; renamed "Multi-Step Tasks" to its own section; removed the Edge Cases section entirely (lock files, merge conflicts, git hooks, etc.).
  - `git_mandate.md`: Restructured with "Requires Approval" now requiring `git status` + `git diff HEAD` before asking, with per-file summary for large diffs; "Always OK" → "No Approval Needed."
  - `journal_mandate.md`: Refined write criteria from "Write if reusable" to "Write if it would help future sessions"; "silently — never ask the user before journaling."

- **Bug Fix: Mutable Default Arguments**:
  - `cli.py`: `str_args: list[str] = []` → `list[str] | None = None` with `if str_args is None: str_args = []`.
  - `subcommand.py`: `paths: list[str] = []` and `nexts: list[str] = []` → `list[str] | None = None` with initialization guards.
  - `file.py`: `replace_map: dict[str, str] = {}` and `excluded_patterns: list[str] = []` → `list[str] | None = None` with initialization guards.

- **Maintenance: Dependency Update**:
  - Updated `pydantic-ai-slim` from `~1.88.0` to `~1.90.0`.
  - Updated `poetry.lock` to match.

- **Tests: Coverage Expansion**:
  - New `test/llm/config/test_limiter.py`: 144 lines for limiter configuration tests.
  - New `test/llm/util/test_stream_response.py`: 400 lines for stream response handling.
  - New `test/util/test_file_util.py`: 35 lines for file utility tests.
  - New `test/util/test_truncate.py`: 75 lines for truncation logic tests.
  - New `test/util/test_yaml.py`: 57 lines for YAML utility tests.

# Older Changelog

- [Changelog v2](./changelog-v2.md)
- [Changelog v1](./changelog-v1.md)
