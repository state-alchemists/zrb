🔖 [Home](../../../README.md) > [Documentation](../../README.md) > [Installation and Configuration](../README.md)

# Configuration

You can configure Zrb by setting up OS Environment Variables, and now you can use `_ZRB_ENV_PREFIX` for white labeling purposes. By default, the prefix is set to `ZRB`.

Environment variables are a standard way to configure software without modifying its code. By setting these variables, you can customize Zrb's behavior to fit your needs and environment.

An environment variable is a user-definable value that can affect the way running processes will behave on a computer.

Many applications (including Zrb) can be configured using environment variables. For Zrb, you can find the list of environment variables [down there](#zrb-environment-variable).

Furthermore, Zrb also allows you to override some configurations with a special singletons.

- [LLM Integration](./llm-integration.md): Integration with LLM
- [LLM Context File (`notes.json`)](../../technical-specs/llm-context.md): Detailed guide on managing persistent, location-aware Notes and Context.
- [LLM Rate Limiter Config](./llm-rate-limiter.md): Configuring LLM rate limiting.
- [Web Auth Config](./web-auth-config.md): Configuring Zrb Web Server authentication programmatically.

## Setting Up Environment Variable

### UNIX-like Systems (Linux, macOS, WSL, Termux)

In UNIX-like systems, you can set environment variables using the following methods:

1. Temporarily (for current session):
   Open a terminal and use the `export` command:

   ```bash
   export VARIABLE_NAME=value
   ```

   For example:
   ```bash
   export ZRB_LOG_LEVEL=DEBUG
   ```

2. Permanently:
   Add the export command to your shell configuration file (e.g., `~/.bashrc`, `~/.zshrc`, or `~/.profile`):

   ```bash
   echo 'export VARIABLE_NAME=value' >> ~/.bashrc
   ```

   Then, reload the configuration:
   ```bash
   source ~/.bashrc
   ```

### Windows

On Windows, you can set environment variables using the following methods:

1. Temporarily (for current session):
   Open a Command Prompt and use the `set` command:

   ```cmd
   set VARIABLE_NAME=value
   ```

   For example:
   ```cmd
   set ZRB_LOG_LEVEL=DEBUG
   ```

2. Permanently:
* Right-click on "This PC" or "My Computer" and select "Properties"
* Click on "Advanced system settings"
* Click on "Environment Variables"
* Under "User variables" or "System variables", click "New"
* Enter the variable name and value, then click "OK"

Alternatively, you can use the `setx` command in Command Prompt (run as administrator):

```cmd
setx VARIABLE_NAME value
```

> **NOTE:** After setting environment variables permanently on Windows, you may need to restart your command prompt or application for the changes to take effect.

### Python

You can also alter Python's environment variable programmatically. Note that this will not change the OS Environment Variable.

This technique is particularly useful if you want to repackage Zrb or configure some things on the fly.

For example, in your `zrb_init.py`, you can hardcode `ZRB_EDITOR` to be `nvim` instead of `nano`.

```python
import os

os.environ["ZRB_EDITOR"] = "nvim"
```

This will alter Zrb behavior, so that whenever it run a text input, it will automatically run `nvim` eventhough OS's `ZRB_EDITOR` is set to `nano`.

You can also use this technique to introduce new environment variables that affect Zrb Configuration.

```python
import os

# Get OS Environment Variable: MY_EDITOR. If not set, get empty string instead.
MY_EDITOR = os.getenv("MY_EDITOR", "")
if MY_EDITOR != "":
    # Only alter ZRB_EDITOR if MY_EDITOR is set
    os.environ["ZRB_EDITOR"] = MY_EDITOR
```

## Zrb Environment Variable

* `ZRB_SHELL`: Sets the shell to use.
    * Default: Determined automatically based on the system
    * Possible values: `zsh`, `bash`, `PowerShell`

* `ZRB_EDITOR`: Sets the default text editor.
    * Default: `nano`
    * Possible values: Any installed text editor

* `DIFF_EDIT_COMMAND`: Template command for diff-based file editing. Used by interactive file replacement tools.
    * Default: Automatically generated based on `ZRB_EDITOR` with support for:
      - Visual Studio Code variants: `code`, `vscode`, `vscodium`, `windsurf`, `cursor`, `zed`, `zeditor`, `agy`
      - `emacs`: Uses ediff-files command
      - `nvim`/`vim`: Enhanced configuration with syntax highlighting and instructions
      - Other editors: Uses `vimdiff` as fallback
    * Template variables: `{old}` (path to old file), `{new}` (path to new file)
    * Possible values: Any command template with `{old}` and `{new}` placeholders

* `ZRB_INIT_MODULES`: Colon-separated list of modules to initialize.
    * Default: Empty
    * Possible values: Any valid module paths separated by colons

* `ZRB_INIT_SCRIPTS`: Colon-separated list of scripts to initialize.
    * Default: Empty
    * Possible values: Any valid script paths separated by colons

* `ZRB_INIT_FILE_NAME`: Init file name.
    * Default: `zrb_init.py`
    * Possible values: Any valid file name relative to directory path.

* `ZRB_ROOT_GROUP_NAME`: Sets the name of the root command group.
    * Default: `zrb`
    * Possible values: Any string

* `ZRB_ROOT_GROUP_DESCRIPTION`: Sets the description of the root command group.
    * Default: `Your Automation Powerhouse`
    * Possible values: Any string

* `ZRB_LOGGING_LEVEL`: Sets the logging level.
    * Default: `WARNING`
    * Possible values: `CRITICAL`, `ERROR`, `WARN`, `WARNING`, `INFO`, `DEBUG`, `NOTSET`

* `ZRB_LOAD_BUILTIN`: Whether to load built-in modules.
    * Default: `1` (true)
    * Possible values: `0` (false), `1` (true)

* `ZRB_WARN_UNRECOMMENDED_COMMAND`: Whether to show warnings for unrecommended commands.
    * Default: `1` (true)
    * Possible values: `0` (false), `1` (true)

* `ZRB_BANNER`: Banner text displayed on startup.
    * Default: Default Zrb banner
    * Possible values: Any string (supports f-string formatting with `{VERSION}`)

* `_ZRB_CUSTOM_VERSION`: Sets a custom version string to override the default version.
    * Default: Empty
    * Possible values: Any string

### Directories and Files

* `ZRB_SESSION_LOG_DIR`: Directory for session logs.
    * Default: `~/.zrb/session`
    * Possible values: Any valid directory path

* `ZRB_TODO_DIR`: Directory for todo files.
    * Default: `~/todo`
    * Possible values: Any valid directory path

### Todo List

* `ZRB_TODO_FILTER`: Filter for todo items.
    * Default: Empty
    * Possible values: Any valid filter string
* `ZRB_TODO_RETENTION`: Retention period for todo items.
    * Default: `2w` (2 weeks)
    * Possible values: Time duration (e.g., `1d` for 1 day, `3w` for 3 weeks, `1m` for 1 month)

### Web Interface

Some Environment variables like `ZRB_WEB_GUEST_USERNAME` and `ZRB_WEB_SUPER_ADMIN_USERNAME` are used as [Web Auth Config](./web-auth-config.md) default property values.

* `ZRB_WEB_FAVICON_PATH`: Favicon path
    * Default: Empty
    * Possible values: Any valid favicon path

* `ZRB_WEB_CSS_PATH`: CSS path
    * Default: Empty
    * Possible values: Any valid CSS path, separated by `:`

* `ZRB_WEB_JS_PATH`: JS path
    * Default: Empty
    * Possible values: Any valid JS path, separated by `:`

* `ZRB_WEB_COLOR`: Web color theme
    * Default: Empty
    * Possible values: Any valid Pico CSS Theme Color, see [Pico CSS docs](https://picocss.com/docs/version-picker)

* `ZRB_WEB_HTTP_PORT`: HTTP port for the web interface.
    * Default: `21213`
    * Possible values: Any valid port number

* `ZRB_WEB_GUEST_USERNAME`: Username for guest access.
    * Default: `user`
    * Possible values: Any valid username string

* `ZRB_WEB_SUPER_ADMIN_USERNAME`: Username for super admin.
    * Default: `admin`
    * Possible values: Any valid username string

* `ZRB_WEB_SUPER_ADMIN_PASSWORD`: Password for super admin.
    * Default: `admin`
    * Possible values: Any valid password string

* `ZRB_WEB_ACCESS_TOKEN_COOKIE_NAME`: Cookie name for access token.
    * Default: `access_token`
    * Possible values: Any valid cookie name

* `ZRB_WEB_REFRESH_TOKEN_COOKIE_NAME`: Cookie name for refresh token.
    * Default: `refresh_token`
    * Possible values: Any valid cookie name

* `ZRB_WEB_SECRET`: Secret key for web interface.
    * Default: `zrb`
    * Possible values: Any string (longer strings provide better security)

* `ZRB_WEB_ENABLE_AUTH`: Whether to enable authentication.
    * Default: `0` (false)
    * Possible values: `0` (false), `1` (true)

* `ZRB_WEB_ACCESS_TOKEN_EXPIRE_MINUTES`: Expiration time for access token in minutes.
    * Default: `30`
    * Possible values: Any positive integer

* `ZRB_WEB_REFRESH_TOKEN_EXPIRE_MINUTES`: Expiration time for refresh token in minutes.
    * Default: `60`
    * Possible values: Any positive integer

* `ZRB_WEB_TITLE`: Title for the web interface.
    * Default: `Zrb`
    * Possible values: Any string

* `ZRB_WEB_JARGON`: Jargon/tagline for the web interface.
    * Default: `Your Automation PowerHouse`
    * Possible values: Any string

* `ZRB_WEB_HOMEPAGE_INTRO`: Introduction text for the web homepage.
    * Default: `Welcome to Zrb Web Interface`
    * Possible values: Any string

### LLM (Language Model) Configuration

The following environment variables are used as LLM configuration default property values.

* `ZRB_LLM_MODEL`: LLM model to use. Use the format `provider:model-name` (e.g., `openai:gpt-4o`, `deepseek:deepseek-reasoner`, `ollama:llama3.1`).
    * Default: None
    * Possible values: Any valid model string with provider prefix. Built-in providers include OpenAI, Anthropic, Google, DeepSeek, Groq, Mistral, and Ollama.

* `ZRB_LLM_SMALL_MODEL`: Smaller/faster LLM model for summarization and auxiliary tasks. Use the format `provider:model-name`.
    * Default: `openai:gpt-4o-mini`
    * Possible values: Any valid model string with provider prefix (e.g., `openai:gpt-4o-mini`, `google:gemini-2.0-flash`, `deepseek:deepseek-chat`)

* `ZRB_LLM_BASE_URL`: Base URL for LLM API.
    * Default: None
    * Possible values: `http://localhost:11434/v1`, `https://api.openai.com/v1`, etc.

* `ZRB_LLM_API_KEY`: API key for the LLM provider.
    * Default: None
    * Possible values: Any valid API key for the chosen provider

* `ZRB_LLM_ASSISTANT_NAME`: Name of the AI assistant.
    * Default: Root group name (e.g., `zrb`)
    * Possible values: Any string

* `ZRB_LLM_ASSISTANT_ASCII_ART`: ASCII art style for the assistant.
    * Default: `default`
    * Possible values: `default`, `none`, or any custom ASCII art string

* `ZRB_LLM_ASSISTANT_JARGON`: Tagline/jargon for the AI assistant.
    * Default: Root group description
    * Possible values: Any string

* `ZRB_LLM_HISTORY_DIR`: Directory to store conversation history.
    * Default: `~/.zrb/llm-history`
    * Possible values: Any valid directory path

* `ZRB_LLM_JOURNAL_DIR`: Directory for LLM journal files (directory-based journaling).
    * Default: `~/.zrb/llm-notes/`
    * Possible values: Any valid directory path
* `ZRB_LLM_JOURNAL_INDEX_FILE`: Index filename for LLM journal (auto-injected into prompts).
    * Default: `index.md`
    * Possible values: Any valid filename

* `ZRB_LLM_PROMPT_DIR`: Directory for custom LLM prompts.
    * Default: `.zrb/llm/prompt`
    * Possible values: Any valid directory path

* `ZRB_LLM_PLUGIN_DIRS`: Colon-separated list of directories containing custom LLM plugins (agents and skills).
    * Default: None
    * Possible values: Any valid directory paths separated by colons (e.g., `/path/to/plugins:/another/path`)

* `ZRB_MCP_CONFIG_FILE`: Path to the MCP configuration file.
    * Default: `mcp-config.json`
    * Possible values: Any valid file path

* `ZRB_LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD`: Token threshold for repository analysis extraction.
    * Default: 40% of the model's maximum context window.
    * Possible values: Any positive integer

* `ZRB_LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD`: Token threshold for repository analysis summarization.
    * Default: 40% of the model's maximum context window.
    * Possible values: Any positive integer

* `ZRB_LLM_FILE_ANALYSIS_TOKEN_THRESHOLD`: Token threshold for file analysis.
    * Default: 40% of the model's maximum context window.
    * Possible values: Any positive integer (previously `ZRB_LLM_FILE_ANALYSIS_TOKEN_LIMIT`)

* `ZRB_USE_TIKTOKEN`: Whether to use Tiktoken for token counting.
    * Default: `1` (true)
    * Possible values: `0` (false), `1` (true)

* `ZRB_TIKTOKEN_ENCODING`: The Tiktoken encoding to use.
    * Default: `cl100k_base`
    * Possible values: Any valid Tiktoken encoding name (e.g., `cl100k_base`, `p50k_base`)

* `ZRB_LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD`: Token threshold for summarizing entire conversation history into structured XML state snapshots.
    * Default: 60% of the model's maximum context window.
    * Possible values: Any positive integer

* `ZRB_LLM_MESSAGE_SUMMARIZATION_TOKEN_THRESHOLD`: Token threshold for summarizing individual large tool call results and messages.
    * Default: 50% of conversational summarization threshold.
    * Possible values: Any positive integer

* `ZRB_LLM_MAX_REQUEST_PER_MINUTE`: Maximum number of LLM requests allowed per minute. Also accepts `ZRB_LLM_MAX_REQUESTS_PER_MINUTE` for backward compatibility.
    * Default: `60`
    * Possible values: Any positive integer (also accepts `ZRB_LLM_MAX_REQUESTS_PER_MINUTE` for backward compatibility)

* `ZRB_LLM_MAX_TOKEN_PER_MINUTE`: Maximum number of LLM tokens allowed per minute. Also accepts `ZRB_LLM_MAX_TOKENS_PER_MINUTE` for backward compatibility.
    * Default: `128000`
    * Possible values: Any positive integer (also accepts `ZRB_LLM_MAX_TOKENS_PER_MINUTE` for backward compatibility)

* `ZRB_LLM_MAX_TOKEN_PER_REQUEST`: Maximum number of tokens allowed per individual LLM request. Also accepts `ZRB_LLM_MAX_TOKENS_PER_REQUEST` for backward compatibility.
    * Default: `128000`
    * Possible values: Any positive integer (also accepts `ZRB_LLM_MAX_TOKENS_PER_REQUEST` for backward compatibility)

* `ZRB_LLM_THROTTLE_SLEEP`: Number of seconds to sleep when throttling is required.
    * Default: `1.0`
    * Possible values: Any positive float

* `ZRB_LLM_HISTORY_SUMMARIZATION_WINDOW`: Number of messages to keep in verbatim before summarizing.
    * Default: `100`
    * Possible values: Any positive integer

* `ZRB_LLM_SHOW_TOOL_CALL_DETAIL`: Whether to show tool call parameters in real-time.
    * Default: `off`
    * Possible values: `on`, `off`

* `ZRB_LLM_SHOW_TOOL_CALL_RESULT`: Whether to show tool call results.
    * Default: `off`
    * Possible values: `on`, `off`

* `ZRB_LLM_INCLUDE_PERSONA`: Whether to include persona prompt in PromptManager.
    * Default: `1` (true)
    * Possible values: `0` (false), `1` (true)

* `ZRB_LLM_INCLUDE_MANDATE`: Whether to include mandate prompt in PromptManager.
    * Default: `1` (true)
    * Possible values: `0` (false), `1` (true)

* `ZRB_LLM_INCLUDE_GIT_MANDATE`: Whether to include git mandate prompt in PromptManager (when inside git repository).
    * Default: `1` (true)
    * Possible values: `0` (false), `1` (true)

* `ZRB_LLM_INCLUDE_SYSTEM_CONTEXT`: Whether to include system context prompt in PromptManager.
    * Default: `1` (true)
    * Possible values: `0` (false), `1` (true)

* `ZRB_LLM_INCLUDE_JOURNAL`: Whether to include journal prompt in PromptManager.
    * Default: `1` (true)
    * Possible values: `0` (false), `1` (true)

* `ZRB_LLM_INCLUDE_CLAUDE_SKILLS`: Whether to include Claude skills prompt in PromptManager.
    * Default: `1` (true)
    * Possible values: `0` (false), `1` (true)

* `ZRB_LLM_INCLUDE_CLI_SKILLS`: Whether to include CLI skills prompt in PromptManager.
    * Default: `0` (false)
    * Possible values: `0` (false), `1` (true)

* `ZRB_LLM_INCLUDE_PROJECT_CONTEXT`: Whether to include project context prompt in PromptManager.
    * Default: `1` (true)
    * Possible values: `0` (false), `1` (true)

### LLM UI Configuration (Pollux)

These variables control the appearance and behavior of the LLM chat interface.

* `ZRB_LLM_UI_STYLE_TITLE_BAR`: Color/Style for the title bar.
* `ZRB_LLM_UI_STYLE_INFO_BAR`: Color/Style for the info bar.
* `ZRB_LLM_UI_STYLE_FRAME`: Color/Style for the UI frames.
* `ZRB_LLM_UI_STYLE_FRAME_LABEL`: Color/Style for frame labels.
* `ZRB_LLM_UI_STYLE_INPUT_FRAME`: Color/Style for the input frame.
* `ZRB_LLM_UI_STYLE_THINKING`: Style for the thinking indicator.
* `ZRB_LLM_UI_STYLE_FAINT`: Style for faint text.
* `ZRB_LLM_UI_STYLE_OUTPUT_FIELD`: Color/Style for the output field.
* `ZRB_LLM_UI_STYLE_INPUT_FIELD`: Color/Style for the input field.
* `ZRB_LLM_UI_STYLE_TEXT`: Default text color/style.
* `ZRB_LLM_UI_STYLE_STATUS`: Style for status indicators.
* `ZRB_LLM_UI_STYLE_BOTTOM_TOOLBAR`: Color/Style for the bottom toolbar.

* `ZRB_LLM_UI_COMMAND_SUMMARIZE`: Commands to trigger history summarization.
    * Default: `/compress, /compact`
* `ZRB_LLM_UI_COMMAND_ATTACH`: Commands to attach files.
    * Default: `/attach`
* `ZRB_LLM_UI_COMMAND_EXIT`: Commands to exit the chat.
    * Default: `/q, /bye, /quit, /exit`
* `ZRB_LLM_UI_COMMAND_INFO`: Commands to show help info.
    * Default: `/info, /help`
* `ZRB_LLM_UI_COMMAND_SAVE`: Commands to save the session.
    * Default: `/save`
* `ZRB_LLM_UI_COMMAND_LOAD`: Commands to load a session.
    * Default: `/load`
* `ZRB_LLM_UI_COMMAND_YOLO_TOGGLE`: Commands to toggle YOLO mode.
    * Default: `/yolo`
* `ZRB_LLM_UI_COMMAND_REDIRECT_OUTPUT`: Commands to redirect last response to file.
    * Default: `>, /redirect`
* `ZRB_LLM_UI_COMMAND_EXEC`: Commands to execute a shell command.
    * Default: `!, /exec`

### RAG (Retrieval-Augmented Generation) Configuration

* `ZRB_RAG_EMBEDDING_API_KEY`: API key for OpenAI embeddings.
    * Default: None
    * Possible values: Any valid OpenAI API key

* `ZRB_RAG_EMBEDDING_BASE_URL`: Base URL for OpenAI API.
    * Default: None
    * Possible values: `https://api.openai.com/v1` or any valid API endpoint

* `ZRB_RAG_EMBEDDING_MODEL`: Embedding model for RAG.
    * Default: `text-embedding-ada-002`
    * Possible values: Any valid embedding model name

* `ZRB_RAG_CHUNK_SIZE`: Chunk size for RAG.
    * Default: `1024`
    * Possible values: Any positive integer

* `ZRB_RAG_OVERLAP`: Overlap size for RAG chunks.
    * Default: `128`
    * Possible values: Any non-negative integer

* `ZRB_RAG_MAX_RESULT_COUNT`: Maximum number of results for RAG.
    * Default: `5`
    * Possible values: Any positive integer

## Search Engine Configuration

* `ZRB_SEARCH_INTERNET_METHOD`: The search engine to use.
    * Default: `serpapi`
    * Possible values: `serpapi`, `searxng`, `brave`

* `SERPAPI_KEY`: API key for SerpAPI.
    * Default: Empty
    * Possible values: Any valid SerpAPI key

* `SERPAPI_LANG`: Language for SerpAPI search results.
    * Default: `en`
    * Possible values: Any valid language code (e.g., `en`, `fr`, `de`, `es`)

* `SERPAPI_SAFE`: Safe search setting for SerpAPI.
    * Default: `off`
    * Possible values: `on`, `off`

* `BRAVE_API_KEY`: API key for Brave Search.
    * Default: Empty
    * Possible values: Any valid Brave Search API key

* `BRAVE_API_LANG`: Language for Brave Search results.
    * Default: `en`
    * Possible values: Any valid language code (e.g., `en`, `fr`, `de`, `es`)

* `BRAVE_API_SAFE`: Safe search setting for Brave Search.
    * Default: `off`
    * Possible values: `off`, `moderate`, `strict`

* `ZRB_SEARXNG_PORT`: Port for the SearXNG instance.
    * Default: `8080`
    * Possible values: Any valid port number

* `ZRB_SEARXNG_BASE_URL`: Base URL for the SearXNG instance.
    * Default: `http://localhost:8080`
    * Possible values: Any valid URL

* `ZRB_SEARXNG_LANG`: Language for SearXNG search results.
    * Default: `en`
    * Possible values: Any valid language code (e.g., `en`, `fr`, `de`, `es`)

* `ZRB_SEARXNG_SAFE`: Safe search setting for SearXNG.
    * Default: `0`
    * Possible values: `0` (off), `1` (moderate), `2` (strict)

* `ZRB_ASCII_ART_DIR`: Directory containing ASCII art files for assistant.

    *   Default: `.zrb/llm/prompt`

    *   Possible values: Any valid directory path



### LLM Hook Configuration



* `ZRB_HOOKS_ENABLED`: Whether to enable the hook system.

    * Default: `1` (true)

    * Possible values: `0` (false), `1` (true)



* `ZRB_HOOKS_DIRS`: Colon-separated list of additional directories to scan for hook configs.

    * Default: Empty

    * Possible values: Any valid directory paths separated by colons



* `ZRB_HOOKS_TIMEOUT`: Default timeout for sync hooks in seconds.

    * Default: `30`

    * Possible values: Any positive integer



* `ZRB_HOOKS_LOG_LEVEL`: Logging level for hook execution.

    * Default: `INFO`

    * Possible values: `CRITICAL`, `ERROR`, `WARN`, `WARNING`, `INFO`, `DEBUG`, `NOTSET`



---
🔖 [Home](../../../README.md) > [Documentation](../../README.md) > [Installation and Configuration](../README.md)
