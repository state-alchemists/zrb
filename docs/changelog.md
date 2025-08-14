🔖 [Home](../../README.md) > [Documentation](../README.md) > [Changelog](README.md)

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
- **Changed**: The `is_yolo_mode` can now be passed when creating a sub-agent.
- **Fixed**: The web runner now no longer inject fake environment variable anymore, it is now correctly use `is_web_mode` parameter while creating a new `SharedContext`, ensuring consistent behavior between web and terminal environments.

# 1.13.3

- **Changed**: The `write_many_files` tool now accepts a list of tuples `(file_path, content)` instead of a dictionary. This improves the tool's predictability and consistency.

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