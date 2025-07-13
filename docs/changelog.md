🔖 [Documentation Home](../README.md) > CI/CD Integration

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
