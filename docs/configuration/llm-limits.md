🔖 [Documentation Home](../README.md) > [Configuration](./) > [LLM Configuration](llm-config.md) > Limits

# LLM Timeouts & Limits

Timeouts, polling intervals and size caps across the agent.

## Table of Contents

- [Timeout Configuration](#timeout-configuration)
- [Interval & Delay Configuration](#interval--delay-configuration)
- [Size & Limit Configuration](#size--limit-configuration)

---

## Timeout Configuration

Task-runtime timings that are not LLM-specific (readiness checks, the scheduler tick, process cleanup, web shutdown) are in [General Environment Variables → Task Runtime](./env-vars.md#task-runtime).

Values are in **milliseconds** unless the row says otherwise.

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_LLM_SSE_KEEPALIVE_TIMEOUT` | How long to wait before sending an SSE keepalive ping (ms) | `60000` |
| `ZRB_LLM_REQUEST_TIMEOUT` | Deadline for one model request, for every agent (main, sub-agent, programmatic). Catches a provider that accepts the connection then stops sending, which no retry detects. `0` disables. (ms) | `300000` |
| `ZRB_LLM_INPUT_QUEUE_TIMEOUT` | Polling interval for the chat input queue (ms) | `500` |
| `ZRB_LLM_SHELL_KILL_WAIT_TIMEOUT` | Time to wait for a shell process to exit after SIGTERM before SIGKILL (ms) | `5000` |
| `ZRB_LLM_BACKGROUND_WAIT_MAX` | Max time a single `GetDelegationResult`/`MonitorProcess` `wait=` call may block before returning "still running" (**seconds**, not ms) | `300` |
| `ZRB_LLM_WEB_PAGE_TIMEOUT` | Playwright page load timeout (ms) | `30000` |
| `ZRB_LLM_WEB_HTTP_TIMEOUT` | HTTP request timeout for web tools and search (ms) | `30000` |
| `ZRB_LLM_MODEL_FETCH_TIMEOUT` | Timeout for fetching Ollama model list (ms) | `5000` |
| `ZRB_LLM_GIT_CMD_TIMEOUT` | Timeout for the git commands that build live/system context — branch, status, log, and the is-a-git-dir probe (ms). Does not apply to agent-invoked git work (snapshots, worktrees). | `5000` |

## Interval & Delay Configuration

All interval and delay values are in **milliseconds**.

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_LLM_UI_STATUS_INTERVAL` | Polling interval for the TUI status loop (ms) | `1000` |
| `ZRB_LLM_UI_LONG_STATUS_INTERVAL` | Interval for updating slow-changing info (CWD, git branch) in TUI (ms) | `60000` |
| `ZRB_LLM_UI_REFRESH_INTERVAL` | Prompt-toolkit application refresh rate (ms) | `500` |
| `ZRB_LLM_UI_FLUSH_INTERVAL` | How often buffered output is flushed to event-driven UIs (ms) | `500` |
| `ZRB_LLM_UI_PASTE_MERGE_WINDOW` | Merge messages submitted within this many ms of the previous one into one — so a multi-line paste in a terminal without bracketed paste does not become one LLM turn per line. `0` disables. | `100` |

## Size & Limit Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_LLM_MAX_COMPLETION_FILES` | Maximum files scanned for path autocompletion | `5000` |
| `ZRB_LLM_MAX_OUTPUT_CHARS` | Maximum characters returned by shell command and file read tools | `100000` |
| `ZRB_LLM_MAX_CONSOLE_OUTPUT_CHARS` | Max characters of a shell command's output mirrored to the console (separate from `ZRB_LLM_MAX_OUTPUT_CHARS`, which caps what the model sees). Output past the cap is still captured and reaches the model. | `100000` |
| `ZRB_LLM_MAX_TOOL_RESULT_CHARS` | Model-facing tool-result threshold (characters). With `ZRB_LLM_ENABLE_TOOL_SPILL=on`, larger results are spilled losslessly to a private local store and replaced by a preview and a `ReadToolResult` handle; otherwise they are flagged `oversized` in app-only metadata and passed through. `0` disables both. | `100000` |
| `ZRB_LLM_ENABLE_TOOL_SPILL` | Enables lossless spill above `ZRB_LLM_MAX_TOOL_RESULT_CHARS`. The payload is stored under the system temp directory; `ReadToolResult` pages it or filters by literal substring. | `off` |
| `ZRB_LLM_HISTORY_MAX_DISPLAY_CHARS` | Maximum characters shown by the `/history` command | `5000` |
| `ZRB_LLM_HISTORY_TRUNCATE_LENGTH` | Maximum chars per field when formatting history entries | `100` |
| `ZRB_LLM_MAX_IMAGE_DIMENSION` | Longest-edge cap (pixels) for attached images before sending to LLM | `1568` |
| `ZRB_LLM_IMAGE_JPEG_QUALITY` | JPEG quality (1-95) for re-encoding photos; PNGs are unaffected | `85` |
| `ZRB_LLM_MAX_ATTACHMENT_BYTES` | Maximum file size (bytes) accepted by `/attach` and the other attachment paths (web chat upload, chat-telegram example) — checked before the file is read. `0` or negative disables the cap. | `20000000` |
| `ZRB_LLM_UI_MAX_BUFFER_SIZE` | Maximum buffered output chars before a forced flush (event-driven UIs) | `2000` |
| `ZRB_LLM_MAX_SKILLS_IN_CATALOG` | Skills listed in the prompt's skill catalogue before truncating with a pointer to `SearchSkill` (which always reaches the rest) — a token-economy cap. `0` or negative lists all. | `10` |
| `ZRB_LLM_MAX_AGENTS_IN_ROSTER` | Sub-agents listed in the delegation tools' AVAILABLE AGENTS roster before truncating with a pointer to `SearchAgent` (which always reaches the rest) — a token-economy cap. `0` or negative lists all. | `10` |
| `ZRB_LLM_MAX_PARALLEL_DELEGATIONS` | Max sub-agent tasks one `DelegateToAgent` fan-out (`tasks=[...]`) runs at once. Each is its own LLM run on the shared rate limiter (and, with `isolate_worktree`, its own git worktree). Paces concurrency, not total: a 50-task call still runs all 50, at most N in flight. `0` or negative disables. | `10` |

> 💡 `ZRB_LLM_MAX_IMAGE_DIMENSION` and `ZRB_LLM_IMAGE_JPEG_QUALITY` also apply to `/photo` captures (see [Voice and Camera → Camera](llm-voice-camera.md#camera)), which are downscaled and re-encoded like pasted or attached images.
