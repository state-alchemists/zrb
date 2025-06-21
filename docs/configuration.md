🔖 [Documentation Home](../README.md) > Configuration

# Configuration

Zrb can be configured using the following environment variables (see "Setting Environment Variables" section below for general instructions):

## General Configuration

- `ZRB_SHELL`: Sets the shell to use.
    - Default: Determined automatically based on the system
    - Possible values: `zsh`, `bash`, `PowerShell`

- `ZRB_EDITOR`: Sets the default text editor.
    - Default: `nano`
    - Possible values: Any installed text editor

- `ZRB_INIT_MODULES`: Colon-separated list of modules to initialize.
    - Default: Empty
    - Possible values: Any valid module paths separated by colons

- `ZRB_INIT_SCRIPTS`: Colon-separated list of scripts to initialize.
    - Default: Empty
    - Possible values: Any valid script paths separated by colons

- `ZRB_INIT_FILE_NAME`: Init file name.
    - Default: `zrb_init.py`
    - Possible values: Any valid file name relative to directory path.

- `ZRB_ROOT_GROUP_NAME`: Sets the name of the root command group.
    - Default: `zrb`
    - Possible values: Any string

- `ZRB_ROOT_GROUP_DESCRIPTION`: Sets the description of the root command group.
    - Default: `Your Automation Powerhouse`
    - Possible values: Any string

- `ZRB_LOGGING_LEVEL`: Sets the logging level.
    - Default: `WARNING`
    - Possible values: `CRITICAL`, `ERROR`, `WARN`, `WARNING`, `INFO`, `DEBUG`, `NOTSET`

- `ZRB_LOAD_BUILTIN`: Whether to load built-in modules.
    - Default: `1` (true)
    - Possible values: `0` (false), `1` (true)

- `ZRB_WARN_UNRECOMMENDED_COMMAND`: Whether to show warnings for unrecommended commands.
    - Default: `1` (true)
    - Possible values: `0` (false), `1` (true)

- `ZRB_BANNER`: Banner text displayed on startup.
    - Default: Default Zrb banner
    - Possible values: Any string (supports f-string formatting with `{VERSION}`)

- `_ZRB_CUSTOM_VERSION`: Sets a custom version string to override the default version.
    - Default: Empty
    - Possible values: Any string

## Directories and Files

- `ZRB_SESSION_LOG_DIR`: Directory for session logs.
    - Default: `~/.zrb-session`
    - Possible values: Any valid directory path

- `ZRB_TODO_DIR`: Directory for todo files.
    - Default: `~/todo`
    - Possible values: Any valid directory path

## Todo List

- `ZRB_TODO_FILTER`: Filter for todo items.
    - Default: Empty
    - Possible values: Any valid filter string
- `ZRB_TODO_RETENTION`: Retention period for todo items.
    - Default: `2w` (2 weeks)
    - Possible values: Time duration (e.g., `1d` for 1 day, `3w` for 3 weeks, `1m` for 1 month)

## Web Interface

- `ZRB_WEB_FAVICON_PATH`: Favicon path
    - Default: Empty
    - Possible values: Any valid favicon path

- `ZRB_WEB_CSS_PATH`: CSS path
    - Default: Empty
    - Possible values: Any valid CSS path, separated by `:`

- `ZRB_WEB_JS_PATH`: JS path
    - Default: Empty
    - Possible values: Any valid JS path, separated by `:`

- `ZRB_WEB_COLOR`: Web color theme
    - Default: Empty
    - Possible values: Any valid Pico CSS Theme Color, see [Pico CSS docs](https://picocss.com/docs/version-picker)

- `ZRB_WEB_HTTP_PORT`: HTTP port for the web interface.
    - Default: `21213`
    - Possible values: Any valid port number

- `ZRB_WEB_GUEST_USERNAME`: Username for guest access.
    - Default: `user`
    - Possible values: Any valid username string

- `ZRB_WEB_SUPERADMIN_USERNAME`: Username for super admin.
    - Default: `admin`
    - Possible values: Any valid username string

- `ZRB_WEB_SUPERADMIN_PASSWORD`: Password for super admin.
    - Default: `admin`
    - Possible values: Any valid password string

- `ZRB_WEB_ACCESS_TOKEN_COOKIE_NAME`: Cookie name for access token.
    - Default: `access_token`
    - Possible values: Any valid cookie name

- `ZRB_WEB_REFRESH_TOKEN_COOKIE_NAME`: Cookie name for refresh token.
    - Default: `refresh_token`
    - Possible values: Any valid cookie name

- `ZRB_WEB_SECRET`: Secret key for web interface.
    - Default: `zrb`
    - Possible values: Any string (longer strings provide better security)

- `ZRB_WEB_ENABLE_AUTH`: Whether to enable authentication.
    - Default: `0` (false)
    - Possible values: `0` (false), `1` (true)

- `ZRB_WEB_ACCESS_TOKEN_EXPIRE_MINUTES`: Expiration time for access token in minutes.
    - Default: `30`
    - Possible values: Any positive integer

- `ZRB_WEB_REFRESH_TOKEN_EXPIRE_MINUTES`: Expiration time for refresh token in minutes.
    - Default: `60`
    - Possible values: Any positive integer

- `ZRB_WEB_TITLE`: Title for the web interface.
    - Default: `Zrb`
    - Possible values: Any string

- `ZRB_WEB_JARGON`: Jargon/tagline for the web interface.
    - Default: `Your Automation PowerHouse`
    - Possible values: Any string

- `ZRB_WEB_HOMEPAGE_INTRO`: Introduction text for the web homepage.
    - Default: `Welcome to Zrb Web Interface`
    - Possible values: Any string

## LLM (Language Model) Configuration

- `ZRB_LLM_MODEL`: LLM model to use.
    - Default: None
    - Possible values: `llama3.1:latest`, `gpt-4`, `gpt-3.5-turbo`, etc.

- `ZRB_LLM_BASE_URL`: Base URL for LLM API.
    - Default: None
    - Possible values: `http://localhost:11434/v1`, `https://api.openai.com/v1`, etc.

- `ZRB_LLM_API_KEY`: API key for the LLM provider.
    - Default: None
    - Possible values: Any valid API key for the chosen provider

- `ZRB_LLM_PERSONA`: LLM persona.
    - Default: None
    - Possible values: Any valid persona prompt

- `ZRB_LLM_SYSTEM_PROMPT`: System prompt for LLM.
    - Default: None
    - Possible values: Any valid system prompt string

- `ZRB_LLM_HISTORY_DIR`: Directory for LLM conversation history files.
    - Default: `~/.zrb-llm-history`
    - Possible values: Any valid directory path

- `ZRB_LLM_ACCESS_LOCAL_FILE`: Whether to allow LLM to access local files.
    - Default: `1` (true)
    - Possible values: `0` (false), `1` (true)

- `ZRB_LLM_ACCESS_INTERNET`: Whether to allow LLM Chat Agent to access internet.
    - Default: `1` (true)
    - Possible values: `0` (false), `1` (true)

- `ZRB_LLM_ACCESS_SHELL`: Whether to allow LLM Chat Agent to access shell.
    - Default: `1` (true)
    - Possible values: `0` (false), `1` (true)

- `ZRB_LLM_SPECIAL_INSTRUCTION_PROMPT`: Special instruction prompt for LLM.
    - Default: None
    - Possible values: Any valid prompt string

- `ZRB_LLM_SUMMARIZATION_PROMPT`: Prompt for summarizing conversation history.
    - Default: None
    - Possible values: Any valid prompt string

- `ZRB_LLM_CONTEXT_ENRICHMENT_PROMPT`: Prompt for enriching context.
    - Default: None
    - Possible values: Any valid prompt string

- `ZRB_LLM_SUMMARIZE_HISTORY`: Whether to summarize conversation history.
    - Default: `1` (true)
    - Possible values: `0` (false), `1` (true)

- `ZRB_LLM_HISTORY_SUMMARIZATION_THRESHOLD`: Threshold for summarizing history (number of messages).
    - Default: `5`
    - Possible values: Any positive integer

- `ZRB_LLM_ENRICH_CONTEXT`: Whether to enrich context.
    - Default: `1` (true)
    - Possible values: `0` (false), `1` (true)

- `ZRB_LLM_CONTEXT_ENRICHMENT_THRESHOLD`: Threshold for enriching context (number of messages).
    - Default: `5`
    - Possible values: Any positive integer

- `ZRB_LLM_MAX_REQUESTS_PER_MINUTE`: Maximum number of LLM requests allowed per minute.
    - Default: `60`
    - Possible values: Any positive integer

- `ZRB_LLM_MAX_TOKENS_PER_MINUTE`: Maximum number of LLM tokens allowed per minute.
    - Default: `120000`
    - Possible values: Any positive integer

- `ZRB_LLM_MAX_TOKENS_PER_REQUEST`: Maximum number of tokens allowed per individual LLM request.
    - Default: `30000`
    - Possible values: Any positive integer

- `ZRB_LLM_THROTTLE_SLEEP`: Number of seconds to sleep when throttling is required.
    - Default: `1.0`
    - Possible values: Any positive float

- `ZRB_LLM_HISTORY_DIR`: Directory for LLM conversation history files.
    - Default: `~/.zrb-llm-history`
    - Possible values: Any valid directory path

- `ZRB_LLM_ALLOW_ACCESS_LOCAL_FILE`: Whether to allow LLM to access local files.
    - Default: `1` (true)
    - Possible values: `0` (false), `1` (true)

- `ZRB_LLM_ALLOW_ACCESS_SHELL`: Whether to allow LLM to access shell.
    - Default: `1` (true)
    - Possible values: `0` (false), `1` (true)

- `ZRB_LLM_ALLOW_ACCESS_INTERNET`: Whether to allow LLM to access internet.
    - Default: `1` (true)
    - Possible values: `0` (false), `1` (true)

## RAG (Retrieval-Augmented Generation) Configuration

- `ZRB_RAG_EMBEDDING_API_KEY`: API key for OpenAI embeddings.
    - Default: None
    - Possible values: Any valid OpenAI API key

- `ZRB_RAG_EMBEDDING_BASE_URL`: Base URL for OpenAI API.
    - Default: None
    - Possible values: `https://api.openai.com/v1` or any valid API endpoint

- `ZRB_RAG_EMBEDDING_MODEL`: Embedding model for RAG.
    - Default: `text-embedding-ada-002`
    - Possible values: Any valid embedding model name

- `ZRB_RAG_CHUNK_SIZE`: Chunk size for RAG.
    - Default: `1024`
    - Possible values: Any positive integer

- `ZRB_RAG_OVERLAP`: Overlap size for RAG chunks.
    - Default: `128`
    - Possible values: Any non-negative integer

- `ZRB_RAG_MAX_RESULT_COUNT`: Maximum number of results for RAG.
    - Default: `5`
    - Possible values: Any positive integer

## SerpAPI Configuration

- `SERPAPI_KEY`: API key for SerpAPI.
    - Default: Empty
    - Possible values: Any valid SerpAPI key

# Setting Environment Variables

Environment variables are a standard way to configure software without modifying its code. By setting these variables, you can customize Zrb's behavior to fit your needs and environment.

An environment variable is a user-definable value that can affect the way running processes will behave on a computer.

Many applications (including Zrb) can be configured using environment variables. Refer to the application documentation for more information. For Zrb, the specific variables are listed above.

## UNIX-like Systems (Linux, macOS, WSL, Termux)

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

## Windows

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
- Right-click on "This PC" or "My Computer" and select "Properties"
- Click on "Advanced system settings"
- Click on "Environment Variables"
- Under "User variables" or "System variables", click "New"
- Enter the variable name and value, then click "OK"

Alternatively, you can use the `setx` command in Command Prompt (run as administrator):

```cmd
setx VARIABLE_NAME value
```

Note: After setting environment variables permanently on Windows, you may need to restart your command prompt or application for the changes to take effect.

