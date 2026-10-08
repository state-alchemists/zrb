🔖 [Documentation Home](../README.md) > [LLM](./) > MCP Support

# MCP Support (Model Context Protocol)

Zrb's LLM agent can connect to external **MCP servers** — tools and data sources exposed via the Model Context Protocol. This lets you extend the assistant with capabilities served by third-party processes (e.g., databases, APIs, local services).

---

## Table of Contents

- [Quick Start](#quick-start)
- [Config File Format](#config-file-format)
- [Server Types](#server-types)
- [Config Discovery](#config-discovery)
- [Configuration Reference](#configuration-reference)

---

## Quick Start

Create a file called `mcp-config.json` in your project directory (or home directory):

```json
{
  "mcpServers": {
    "my-tool": {
      "command": "npx",
      "args": ["-y", "@my-org/my-mcp-server"],
      "env": {
        "API_KEY": "${MY_API_KEY}"
      }
    }
  }
}
```

That's it. The next time you run `zrb llm chat`, Zrb will automatically load this server and make its tools available to the assistant. MCP tools are deferred-loaded: their schemas stay out of each request until the model searches for them by name, so a server with many tools doesn't add to every turn's token cost.

A user-built `LLMTask`/`LLMChatTask` gets MCP servers only after [`apply_common_tools(host)`](extending-the-llm.md#equipping-a-custom-host-with-the-shipped-tool-surface).

---

## Config File Format

The format is the same as [Claude Desktop's MCP configuration](https://modelcontextprotocol.io/docs/getting-started), so you can reuse configs directly.

```json
{
  "mcpServers": {
    "<server-name>": {
      "command": "node",
      "args": ["path/to/server.js"],
      "env": { "KEY": "value" }
    },
    "<another-server>": {
      "url": "http://localhost:8080/mcp"
    }
  }
}
```

An entry with `command` is a stdio server (subprocess); an entry with `url` is an HTTP server. The file must be plain JSON — no comments.

Environment variable placeholders — `${VAR_NAME}`, or `${VAR_NAME:-default}` — in `command`, `args`, `env`, and `url` values are expanded when the config is loaded. A placeholder whose variable is unset and has no default makes zrb skip that server with a warning.

---

## Server Types

### Stdio (subprocess)

The most common type. Zrb spawns the server as a child process and communicates over stdin/stdout.

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    },
    "postgres": {
      "command": "uvx",
      "args": ["mcp-server-postgres", "--connection-string", "${DATABASE_URL}"]
    }
  }
}
```

Required fields: `command`. Optional: `args`, `env`.

### HTTP (Streamable HTTP or SSE)

For servers already running as an HTTP service.

```json
{
  "mcpServers": {
    "remote-tool": {
      "url": "https://my-mcp-server.example.com/mcp"
    },
    "legacy-sse-tool": {
      "url": "https://legacy.example.com/sse"
    }
  }
}
```

Required fields: `url`. A URL ending in `/sse` uses the SSE transport; any other URL uses Streamable HTTP.

---

## Config Discovery

Zrb discovers MCP configs by traversing downward from the home directory to the current working directory, loading every config file it finds along the way. **Later files override earlier ones** for servers with the same name, so project-level configs can override user-level ones.

**Example traversal** (for cwd = `~/projects/myapp/backend`):

| Path | Loaded? |
|------|---------|
| `~/mcp-config.json` | Yes — user-global defaults |
| `~/projects/mcp-config.json` | Yes — workspace defaults |
| `~/projects/myapp/mcp-config.json` | Yes — app-level config |
| `~/projects/myapp/backend/mcp-config.json` | Yes — service-level config (highest priority) |

> If cwd is outside the home directory, only the cwd's config file is loaded.

---

## Configuration Reference

| Environment Variable | Default | Description |
|---|---|---|
| `ZRB_MCP_CONFIG_FILE` | `mcp-config.json` | Filename to look for in each directory during traversal |
| `ZRB_LLM_MCP_MAX_RETRIES` | `3` | Max times a failing MCP tool call may be retried |

To change the config filename globally:

```bash
export ZRB_MCP_CONFIG_FILE=".mcp.json"
```

Or in code:

```python
from zrb.config.config import CFG
CFG.MCP_CONFIG_FILE = ".mcp.json"
```

---

🔖 [Documentation Home](../README.md) > [LLM](./) > MCP Support
