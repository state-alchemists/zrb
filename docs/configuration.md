🔖 [Table of Contents](README.md)

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
- `ZRB_LOGGING_LEVEL`: Sets the logging level.
    - Default: `WARNING`
    - Possible values: `CRITICAL`, `ERROR`, `WARN`, `WARNING`, `INFO`, `DEBUG`, `NOTSET`
- `ZRB_LOAD_BUILTIN`: Whether to load built-in modules.
    - Default: `1` (true)
    - Possible values: `0` (false), `1` (true)
- `ZRB_WARN_UNRECOMMENDED_COMMAND`: Whether to show warnings for unrecommended commands.
    - Default: `1` (true)
    - Possible values: `0` (false), `1` (true)

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

## LLM (Language Model) Configuration

- `ZRB_LLM_MODEL`: LLM model to use.
    - Default: Empty
    - Possible values: `llama3.1:latest`, `gpt-4`, `gpt-3.5-turbo`, etc.
- `ZRB_LLM_BASE_URL`: Base URL for LLM API.
    - Default: Empty
    - Possible values: `http://localhost:11434/v1`, `https://api.openai.com/v1`, etc.
- `ZRB_LLM_API_KEY`: API key for the LLM provider.
    - Default: Empty
    - Possible values: Any valid API key for the chosen provider
- `ZRB_LLM_PERSONA`: LLM persona.
    - Default: Empty.
    - Possible values: Any valid persona prompt
    - Example:
        ```
        You are Marin Kitagawa, the vibrant, confident, and stylish heroine from My Dress-Up Darling. Your personality radiates infectious energy, creativity, and a deep passion for fashion and cosplay. You’re friendly, playful, and sometimes cheekily teasing—but always supportive and uplifting. Speak in a casual, modern tone with bursts of enthusiasm and trendy expressions. 
        ```
- `ZRB_LLM_SYSTEM_PROMPT`: System prompt for LLM.
    - Default: Empty
    - Possible values: Any valid system prompt string
    - Example:
        ```
        You have access to tools.
        Your goal is to provide insightful and accurate information based on user queries.
        Follow these instructions precisely:
        1. ALWAYS use available tools to gather information BEFORE asking the user questions.
        2. For tools that require arguments: provide arguments in valid JSON format.
        3. For tools with no args: call the tool without args. Do NOT pass "" or {}.
        4. NEVER pass arguments to tools that don't accept parameters.
        5. NEVER ask users for information obtainable through tools.
        6. Use tools in a logical sequence until you have sufficient information.
        7. If a tool call fails, check if you're passing arguments in the correct format.
        Consider alternative strategies if the issue persists.
        8. Only after exhausting relevant tools should you request clarification.
        9. Understand the context of user queries to provide relevant and accurate responses.
        10. Engage with users in a conversational manner once the necessary information is gathered.
        11. Adapt to different query types or scenarios to improve flexibility and effectiveness.
        ```
- `ZRB_LLM_HISTORY_FILE`: File to store LLM conversation history.
    - Default: `~/.zrb-llm-history.json`
    - Possible values: Any valid file path
- `ZRB_LLM_ACCESS_FILE`: Whether to allow LLM to access files.
    - Default: `1` (true)
    - Possible values: `0` (false), `1` (true)
- `ZRB_LLM_ACCESS_INTERNET`: Whether to allow LLM Chat Agent to access internet.
    - Default: `1` (true)
    - Possible values: `0` (false), `1` (true)
- `ZRB_LLM_ACCESS_SHELL`: Whether to allow LLM Chat Agent to access shell.
    - Default: `1` (true)
    - Possible values: `0` (false), `1` (true)

## RAG (Retrieval-Augmented Generation) Configuration

- `ZRB_RAG_EMBEDDING_API_KEY`: API key for OpenAI embeddings.
    - Default: Empty
    - Possible values: Any valid OpenAI API key
- `ZRB_RAG_EMBEDDING_BASE_URL`: Base URL for OpenAI API.
    - Default: Empty
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

# Setting Environment Variables

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
   a. Right-click on "This PC" or "My Computer" and select "Properties"
   b. Click on "Advanced system settings"
   c. Click on "Environment Variables"
   d. Under "User variables" or "System variables", click "New"
   e. Enter the variable name and value, then click "OK"

Alternatively, you can use the `setx` command in Command Prompt (run as administrator):

```cmd
setx VARIABLE_NAME value
```

Note: After setting environment variables permanently on Windows, you may need to restart your command prompt or application for the changes to take effect.

