🔖 [Table of Contents](README.md)

# Configuration

Zrb can be configured using the following [environment variables](recipes/others/setup-environment-variables.md):

## General Configuration

- `ZRB_SHELL`: Sets the shell to use. Default is determined automatically based on the system (i.e., `zsh`, `bash`, `PowerShell`).
- `ZRB_EDITOR`: Sets the default text editor. Default: `nano`
- `ZRB_INIT_MODULES`: Colon-separated list of modules to initialize.
- `ZRB_INIT_SCRIPTS`: Colon-separated list of scripts to initialize.
- `ZRB_LOGGING_LEVEL`: Sets the logging level. Possible values: CRITICAL, ERROR, WARN, WARNING, INFO, DEBUG, NOTSET. Default: WARNING
- `ZRB_LOAD_BUILTIN`: Whether to load built-in modules. Default: `1` (true)
- `ZRB_SHOW_TIME`: Whether to show time in logs. Default: `1` (true)
- `ZRB_WARN_UNRECOMMENDED_COMMAND`: Whether to show warnings for unrecommended commands. Default: `1` (true)

## Directories and Files

- `ZRB_SESSION_LOG_DIR`: Directory for session logs. Default: `~/.zrb-session`
- `ZRB_TODO_DIR`: Directory for todo files. Default: `~/todo`

## Todo List

- `ZRB_TODO_FILTER`: Filter for todo items. Default: empty
- `ZRB_TODO_RETENTION`: Retention period for todo items. Default: `2w` (2 weeks)

## Web Interface

- `ZRB_WEB_HTTP_PORT`: HTTP port for the web interface. Default: `21213`
- `ZRB_WEB_GUEST_USERNAME`: Username for guest access. Default: `user`
- `ZRB_WEB_SUPERADMIN_USERNAME`: Username for super admin. Default: `admin`
- `ZRB_WEB_SUPERADMIN_PASSWORD`: Password for super admin. Default: `admin`
- `ZRB_WEB_ACCESS_TOKEN_COOKIE_NAME`: Cookie name for access token. Default: `access_token`
- `ZRB_WEB_REFRESH_TOKEN_COOKIE_NAME`: Cookie name for refresh token. Default: `refresh_token`
- `ZRB_WEB_SECRET`: Secret key for web interface. Default: `zrb`
- `ZRB_WEB_ENABLE_AUTH`: Whether to enable authentication. Default: `0` (false)
- `ZRB_WEB_ACCESS_TOKEN_EXPIRE_MINUTES`: Expiration time for access token in minutes. Default: `30`
- `ZRB_WEB_REFRESH_TOKEN_EXPIRE_MINUTES`: Expiration time for refresh token in minutes. Default: `60`

## LLM (Language Model) Configuration

- `ZRB_LLM_MODEL`: LLM model to use. Default: `ollama_chat/llama3.1`
- `ZRB_LLM_SYSTEM_PROMPT`: System prompt for LLM. Default: `You are a helpful assistant`
- `ZRB_LLM_HISTORY_FILE`: File to store LLM conversation history. Default: `~/.zrb-llm-history.json`
- `ZRB_LLM_ACCESS_FILE`: Whether to allow LLM to access files. Default: `1` (true)
- `ZRB_LLM_ACCESS_WEB`: Whether to allow LLM to access web. Default: `1` (true)

## RAG (Retrieval-Augmented Generation) Configuration

- `ZRB_RAG_EMBEDDING_MODEL`: Embedding model for RAG. Default: `ollama/nomic-embed-text`
- `ZRB_RAG_CHUNK_SIZE`: Chunk size for RAG. Default: `1024`
- `ZRB_RAG_OVERLAP`: Overlap size for RAG chunks. Default: `128`
- `ZRB_RAG_MAX_RESULT_COUNT`: Maximum number of results for RAG. Default: `5`

🔖 [Table of Contents](README.md)
